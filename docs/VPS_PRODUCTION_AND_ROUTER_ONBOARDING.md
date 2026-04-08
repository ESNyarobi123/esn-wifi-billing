# VPS production + router onboarding guide

This guide captures the working flow we proved locally and turns it into a repeatable production checklist for:

- VPS IP: `139.84.240.120`
- public domain: `skywifibill.spotbox.online`
- ESN web portal + admin on the VPS
- MikroTik router onboarding through **Generate router provisioning package**

It is written for two goals:

1. deploy the app online without forgetting the important env / DNS details
2. onboard a new router safely, including what to do before `Push to router`

---

## 1. Current project status

As of this document:

- Real MikroTik mode is working (`MIKROTIK_USE_MOCK=false`)
- router test connection works against a real router
- provisioning package generation works
- `Push to router` works when the router is prepared correctly
- captive portal popup opens and redirects into the ESN web portal
- hotspot context (`MAC`, `IP`, router/site IDs) is carried into the web flow
- captive portal UI was simplified to a phone-first flow

Known open item:

- ClickPesa live payment is enabled in the app, but token generation is currently returning `HTTP 403 Forbidden`
- this usually means **wrong ClickPesa API key** or **IP whitelist missing**
- when you move to the VPS, ask ClickPesa to whitelist `139.84.240.120` if they enforce source-IP restrictions

---

## 2. Production deployment target

Recommended public layout for this project:

- `https://skywifibill.spotbox.online/` -> Next.js web app
- `https://skywifibill.spotbox.online/api/...` -> FastAPI

This matches the repo nginx snippet in [infra/nginx/example.conf](/Users/eunice/MY/esn-wifi-billing/infra/nginx/example.conf) and works well with the frontend API helper in [apps/web/src/lib/config.ts](/Users/eunice/MY/esn-wifi-billing/apps/web/src/lib/config.ts).

Important: for this app, `NEXT_PUBLIC_API_URL` should be the **origin only**, not `/api`.

Correct:

```env
NEXT_PUBLIC_API_URL=https://skywifibill.spotbox.online
```

Wrong:

```env
NEXT_PUBLIC_API_URL=https://skywifibill.spotbox.online/api
```

The frontend already appends `/api/v1/...` internally.

---

## 3. VPS checklist

### 3.1 DNS

Create an `A` record:

- `skywifibill.spotbox.online -> 139.84.240.120`

### 3.2 Open ports

Open only the ports you really need:

- `22` for SSH
- `80` for HTTP
- `443` for HTTPS

Recommended hardening:

- do not leave `3000` and `8000` publicly exposed long-term
- either protect them with the VPS firewall or change Docker publishing before going fully live

### 3.3 Reverse proxy

Use nginx or another reverse proxy on the VPS for:

- TLS termination
- `/api/` -> FastAPI on port `8000`
- `/` -> Next.js on port `3000`

The repo already includes a starting point in [infra/nginx/example.conf](/Users/eunice/MY/esn-wifi-billing/infra/nginx/example.conf).

For your domain, the important part is:

```nginx
server_name skywifibill.spotbox.online;
```

### 3.4 Production `.env`

Before launch, update [`.env`](/Users/eunice/MY/esn-wifi-billing/.env) for production values like these:

```env
API_ENV=production

CORS_ORIGINS=https://skywifibill.spotbox.online
TRUSTED_HOSTS=skywifibill.spotbox.online

NEXT_PUBLIC_API_URL=https://skywifibill.spotbox.online
INTERNAL_API_URL=http://api:8000

MIKROTIK_USE_MOCK=false
MIKROTIK_USE_ROUTEROS_REST_STUB=false

CLICKPESA_ENABLED=true
DEFAULT_PAYMENT_PROVIDER=clickpesa
CLICKPESA_API_BASE_URL=https://api.clickpesa.com
CLICKPESA_CLIENT_ID=...
CLICKPESA_API_KEY=...
CLICKPESA_CHECKSUM_KEY=...
```

Also make sure these are set securely:

- `JWT_SECRET_KEY`
- `ROUTER_CREDENTIALS_FERNET_KEY`
- `POSTGRES_PASSWORD`

Notes:

- `NEXT_PUBLIC_API_URL` is a **build-time** value for the web app, so if you change it you must rebuild the `web` image
- `INTERNAL_API_URL` is runtime-only and should stay `http://api:8000` in Docker
- use `CLICKPESA_API_KEY` if ClickPesa gave you an API key; do not assume a generic secret field is enough

### 3.5 Deploy commands

From the repo root on the VPS:

```bash
docker compose up -d --build
```

If you change only backend/runtime env later:

```bash
docker compose up -d --force-recreate api worker beat
```

If you change `NEXT_PUBLIC_API_URL`:

```bash
docker compose up -d --build web
```

### 3.6 Smoke checks

After deploy, confirm:

```bash
curl -I http://127.0.0.1:3000
curl -I http://127.0.0.1:8000/api/v1/health/live
curl -I https://skywifibill.spotbox.online
curl -I https://skywifibill.spotbox.online/api/v1/health/live
```

Then run the repo smoke flow from [apps/web/docs/STAGING.md](/Users/eunice/MY/esn-wifi-billing/apps/web/docs/STAGING.md).

---

## 4. Router onboarding overview

The safe onboarding flow is:

1. add the router in the ESN admin
2. confirm `Test connection` is really talking to the router
3. prepare the router network if needed
4. fill **Generate router provisioning package**
5. start with `Download zip` if you are unsure
6. use `Push to router` when the router is prepared and FTP/API are ready
7. verify HotSpot and test on a phone

Very important:

- `Portal base URL` is the ESN app on the VPS
- `API base URL` is the public API origin the portal will call
- `HotSpot DNS name` is the captive-portal hostname on the router, which is a different concern from the VPS portal domain

---

## 5. Remote routers over WireGuard

If the router is not on the same LAN as the VPS, `Test connection` will show `offline` until the VPS can reach the router.

For this project, the best fix is:

- VPS acts as the reachable WireGuard endpoint
- MikroTik connects out to the VPS
- ESN stores the router host as the **WireGuard IP**, not the local LAN IP

Recommended tunnel plan:

- VPS public IP: `139.84.240.120`
- WireGuard UDP port: `51820`
- WireGuard subnet: `10.200.0.0/24`
- VPS WireGuard IP: `10.200.0.1/24`
- MikroTik WireGuard IP: `10.200.0.2/24`

After the tunnel is up, add the router in ESN like this:

- `Host` = `10.200.0.2`
- `API port` = `8728` or `8729`
- `Username` / `Password` = the real router admin credentials

### 5.1 VPS setup

Assumption:

- VPS OS is Debian/Ubuntu-based

Install WireGuard:

```bash
apt update
apt install -y wireguard qrencode
umask 077
wg genkey | tee /etc/wireguard/esn-vps.key | wg pubkey > /etc/wireguard/esn-vps.pub
cat /etc/wireguard/esn-vps.pub
```

Create `/etc/wireguard/wg-esn.conf`:

```ini
[Interface]
Address = 10.200.0.1/24
ListenPort = 51820
PrivateKey = REPLACE_WITH_CONTENTS_OF_/etc/wireguard/esn-vps.key

[Peer]
PublicKey = REPLACE_WITH_MIKROTIK_PUBLIC_KEY
AllowedIPs = 10.200.0.2/32
PersistentKeepalive = 25
```

Bring it up:

```bash
systemctl enable wg-quick@wg-esn
systemctl start wg-quick@wg-esn
wg show
ip addr show wg-esn
```

If you use UFW:

```bash
ufw allow 51820/udp
```

### 5.2 MikroTik setup

Create the WireGuard interface and give it the tunnel IP.

```rsc
/interface wireguard
add name=wg-esn listen-port=51820

/ip address
add address=10.200.0.2/24 interface=wg-esn comment="ESN WireGuard"
```

Print the MikroTik public key:

```rsc
/interface wireguard print detail where name="wg-esn"
```

Take the `public-key` from that output and place it into the VPS config as `PublicKey`.

Then print the VPS public key:

```bash
cat /etc/wireguard/esn-vps.pub
```

Add the VPS as a peer on MikroTik:

```rsc
/interface wireguard peers
add interface=wg-esn public-key="PASTE_VPS_PUBLIC_KEY" allowed-address=10.200.0.1/32 endpoint-address=139.84.240.120 endpoint-port=51820 persistent-keepalive=25s
```

### 5.3 Router firewall rules

MikroTik’s official docs note that default firewall rules can block WireGuard traffic or access to router services, so allow the WireGuard subnet in the input chain before drop rules.

Use:

```rsc
/ip firewall filter
add action=accept chain=input protocol=udp dst-port=51820 comment="allow WireGuard UDP"
add action=accept chain=input src-address=10.200.0.0/24 comment="allow ESN WireGuard management"
```

Optional hardening for router services:

```rsc
/ip service set api address=10.200.0.0/24
/ip service set ftp address=10.200.0.0/24
```

If using API over TLS:

```rsc
/ip service set api disabled=yes
/ip service set api-ssl disabled=no port=8729 address=10.200.0.0/24
/ip service set ftp address=10.200.0.0/24
```

### 5.4 Verify the tunnel

On VPS:

```bash
wg show
ping -c 3 10.200.0.2
nc -vz 10.200.0.2 8728
nc -vz 10.200.0.2 21
```

On MikroTik:

```rsc
/interface wireguard print detail where name="wg-esn"
/interface wireguard peers print detail
/ping 10.200.0.1
```

When the tunnel is healthy:

- `latest-handshake` should update
- VPS should ping `10.200.0.2`
- API and FTP ports should answer over the WireGuard IP

Only after this should you add or update the router inside ESN and expect `Test connection` to turn `online`.

---

## 6. Before you add a router in ESN

On the MikroTik, decide whether this router is:

- a **fresh router** dedicated to hotspot onboarding
- or an **already-live router** with existing LAN, bridge, DHCP, and Wi-Fi

Why this matters:

- `Push to router` can safely build HotSpot on a dedicated interface/bridge
- it is risky to point it at a live bridge that already has default DHCP or production users

If the router already has normal LAN on `bridge` with existing DHCP:

- do **not** use the main `bridge` as your HotSpot interface blindly
- create a separate `bridge-hotspot` first and move only the hotspot radio/ports into it

---

## 7. Router prerequisites before `Push to router`

### 7.1 Enable MikroTik services

The ESN app needs:

- RouterOS API access for connection, verification, and import
- FTP access for uploading hotspot files and `router-provisioning.rsc`

On the router, enable one of these API modes:

- plain API: port `8728`
- TLS API: port `8729`

And enable FTP:

```rsc
/ip service set api disabled=no port=8728
/ip service set api-ssl disabled=yes
/ip service set ftp disabled=no port=21
```

If you want TLS API instead:

```rsc
/ip service set api disabled=yes
/ip service set api-ssl disabled=no port=8729
/ip service set ftp disabled=no port=21
```

Then confirm the router credentials you store in ESN are correct.

### 7.2 Recommended new-router prep

For a fresh router, the recommended design is:

- `ether1` = WAN
- `bridge-hotspot` = guest network bridge
- `wlan1` or another chosen port/radio = guest hotspot side
- guest subnet = `10.10.10.1/24`

If `wlan1` is your hotspot radio, these commands are a good starting point:

```rsc
:if ([:len [/interface bridge find where name="bridge-hotspot"]] = 0) do={/interface bridge add name="bridge-hotspot" comment="ESN hotspot bridge"}
/interface bridge port remove [find where interface="wlan1"]
:if ([:len [/interface bridge port find where bridge="bridge-hotspot" and interface="wlan1"]] = 0) do={/interface bridge port add bridge="bridge-hotspot" interface="wlan1"}
/interface wireless set [find where name="wlan1"] mode=ap-bridge ssid="YOUR HOTSPOT SSID" disabled=no
:if ([:len [/ip address find where address="10.10.10.1/24" and interface="bridge-hotspot"]] = 0) do={/ip address add address="10.10.10.1/24" interface="bridge-hotspot" comment="ESN hotspot gateway"}
:if ([:len [/ip pool find where name="esn-pool-hq"]] = 0) do={/ip pool add name="esn-pool-hq" ranges="10.10.10.10-10.10.10.250"} else={/ip pool set [find where name="esn-pool-hq"] ranges="10.10.10.10-10.10.10.250"}
:if ([:len [/ip dhcp-server network find where address="10.10.10.0/24"]] = 0) do={/ip dhcp-server network add address="10.10.10.0/24" gateway="10.10.10.1" dns-server="10.10.10.1" comment="ESN hotspot subnet"} else={/ip dhcp-server network set [find where address="10.10.10.0/24"] gateway="10.10.10.1" dns-server="10.10.10.1" comment="ESN hotspot subnet"}
:if ([:len [/ip dhcp-server find where name="esn-dhcp-hq"]] = 0) do={/ip dhcp-server add name="esn-dhcp-hq" interface="bridge-hotspot" address-pool="esn-pool-hq" lease-time=1h disabled=no} else={/ip dhcp-server set [find where name="esn-dhcp-hq"] interface="bridge-hotspot" address-pool="esn-pool-hq" lease-time=1h disabled=no}
```

Adapt these placeholders when needed:

- replace `wlan1` if your hotspot radio is different
- replace the SSID `YOUR HOTSPOT SSID`
- replace the subnet only if you want a different hotspot LAN

### 7.3 Verify router prep

Before `Push to router`, these checks should look sane:

```rsc
/interface bridge port print where bridge="bridge-hotspot"
/ip address print where interface="bridge-hotspot"
/ip dhcp-server print where name="esn-dhcp-hq"
/interface wireless print where name="wlan1"
```

If these are wrong, fix the router first, then push.

---

## 8. Add the router in ESN admin

On the Routers page:

- choose the correct site
- set router IP/host
- choose API port:
  - `8728` for plain API
  - `8729` for API over TLS
- set TLS checkbox to match the port
- enter username and password

Then:

1. save the router
2. open router detail
3. click `Test connection`

Do not continue until:

- the real router shows `online`
- wrong/fake details show `offline`

If everything shows `online`, check that the app is not accidentally in mock mode. Real production mode requires:

- `MIKROTIK_USE_MOCK=false`

---

## 9. How to fill **Generate router provisioning package**

The form lives in [apps/web/src/components/routers/router-provisioning-download.tsx](/Users/eunice/MY/esn-wifi-billing/apps/web/src/components/routers/router-provisioning-download.tsx).

Use these values for a production deployment on your VPS.

### 9.1 Recommended production values

For the ESN VPS itself:

- `Portal base URL` = `https://skywifibill.spotbox.online`
- `API base URL` = `https://skywifibill.spotbox.online`

That is correct when nginx serves:

- `/` -> web
- `/api/` -> api

### 9.2 Field-by-field guide

#### Portal base URL

What it means:

- where the user is redirected after the hotspot popup opens

For production:

```text
https://skywifibill.spotbox.online
```

#### API base URL

What it means:

- the public browser/API origin the ESN portal uses
- this host is also added to the router walled garden

For production with same-domain nginx:

```text
https://skywifibill.spotbox.online
```

If you later split the API to a different host, use that exact public API origin instead.

#### HotSpot interface

What it means:

- the router interface or bridge carrying guest hotspot clients

Recommended:

```text
bridge-hotspot
```

Do not point this to a main live bridge unless you fully understand the impact.

#### WAN interface

What it means:

- the internet uplink used for masquerade/NAT

Common value:

```text
ether1
```

#### LAN gateway / CIDR

What it means:

- the guest hotspot gateway IP and subnet

Recommended:

```text
10.10.10.1/24
```

#### HotSpot DNS name

What it means:

- the captive-portal hostname served by the router

Recommended choices:

- private/local router: `login.hq.wifi.local`
- public router with its own public DNS and certificate plan: `login.hq.skywifibill.spotbox.online`

Important:

- this is **not automatically the same thing** as your VPS portal domain
- if you want to use `Attempt Let's Encrypt`, the public DNS for this hostname must resolve to the router itself, not the VPS

#### DHCP pool start / end

Recommended:

```text
10.10.10.10
10.10.10.250
```

They must stay inside the chosen subnet.

#### HotSpot files directory

Recommended:

- `flash/esn-hotspot-hq` if the router has persistent flash storage
- `esn-hotspot-hq` if it does not

For most RouterBOARD devices with `flash`, prefer:

```text
flash/esn-hotspot-hq
```

#### SSL certificate name

Use this only if the certificate already exists on the router.

Otherwise:

- leave it blank
- keep `Attempt Let's Encrypt` off unless the router has public DNS and inbound port `80`

#### Extra walled-garden hosts

Use this only when guests must access extra hosts before authentication, for example:

- payment gateway domains
- CDN/logo domains
- extra API hosts

If not needed, leave it empty.

#### Provider templates

Current recommended value:

```text
clickpesa
```

This adds known provider hosts to the walled garden automatically.

#### Create DNS static record

Recommended:

- `ON`

This maps the chosen HotSpot DNS name to the router guest gateway automatically.

#### Attempt Let's Encrypt

Recommended default:

- `OFF`

Turn it on only if:

- the hotspot DNS hostname has public DNS
- that hostname resolves to the router
- port `80` is reachable from the internet to the router

---

## 10. `Download zip` vs `Push to router`

### Download zip

Use this when:

- you are onboarding a router for the first time
- you want to review the script before import
- you are not fully sure about interface names

The zip includes:

- `router-provisioning.rsc`
- `hotspot-files/`
- `README.txt`

### Push to router

Use this when:

- router API already works
- FTP is enabled on the router
- the credentials in ESN are correct
- the HotSpot interface and WAN interface are correct
- the router is already prepared for safe hotspot deployment

What it does internally:

1. uploads hotspot files through FTP
2. uploads `router-provisioning.rsc`
3. runs RouterOS `/import`
4. verifies HotSpot profile/server and DNS static records

This logic lives in [services/api/app/modules/routers/provisioning_push_service.py](/Users/eunice/MY/esn-wifi-billing/services/api/app/modules/routers/provisioning_push_service.py).

---

## 11. Post-push verification on the router

After a successful push, verify:

```rsc
/ip hotspot print
/ip hotspot profile print
/ip hotspot walled-garden print
/ip hotspot walled-garden ip print
/ip dns static print
/file print where name~"esn-hotspot"
```

Expected signs:

- hotspot server exists
- hotspot profile exists
- DNS static record exists for the hotspot DNS name
- hotspot files exist on the router
- walled garden entries include the ESN portal host and any provider hosts

---

## 12. Real phone test after push

Use a real phone or laptop:

1. connect to the hotspot SSID
2. confirm it gets an IP from the hotspot subnet, for example `10.10.10.x`
3. open `http://neverssl.com` if the popup does not appear immediately
4. confirm the captive portal opens
5. confirm the ESN page loads
6. choose a plan and test the flow

Useful router commands while testing:

```rsc
/ip dhcp-server lease print where address~"10.10.10."
/ip hotspot host print
/ip hotspot active print
/ip hotspot walled-garden print
/ip hotspot walled-garden ip print
```

---

## 13. If `Push to router` fails

These are the first things to check.

### Case 1: router says offline or test connection fails

Check:

- correct router IP
- correct API port `8728` or `8729`
- TLS checkbox matches the port
- API service enabled on the router
- username/password are correct
- `MIKROTIK_USE_MOCK=false`

### Case 2: router log shows `login failure for user ... via api`

Usually this means:

- wrong credentials on that router record
- or a fake/old router entry is still active in ESN and background jobs keep trying it

If the wrong router entry remains in the system, delete it or mark it deleted.

### Case 3: push fails even though test connection works

Usually this is one of:

- FTP is disabled on the router
- HotSpot interface name is wrong
- the chosen interface already has conflicting LAN/DHCP setup
- the router user does not have enough privileges

### Case 4: main bridge already has live DHCP / LAN

Do not push onto that bridge blindly.

Instead:

- create `bridge-hotspot`
- move only the guest Wi-Fi/ports into it
- keep the main production bridge untouched

### Case 5: captive popup opens but page says `ERR_CONNECTION_REFUSED`

Usually this means:

- portal host is not reachable from the hotspot
- the app is still pointing to `localhost`
- the walled garden host/IP rules are missing
- the VPS or local portal host is down

### Case 6: payment shows `provider http 403`

This is a ClickPesa auth problem, not a hotspot UI problem.

Check:

- `CLICKPESA_CLIENT_ID`
- `CLICKPESA_API_KEY`
- `CLICKPESA_CHECKSUM_KEY`
- ClickPesa IP whitelist

For VPS production, ask ClickPesa to allow:

```text
139.84.240.120
```

---

## 14. Recommended values for your production onboarding

If you are onboarding a new router and using a separate guest bridge, this is the safest starting profile:

- `Portal base URL` = `https://skywifibill.spotbox.online`
- `API base URL` = `https://skywifibill.spotbox.online`
- `HotSpot interface` = `bridge-hotspot`
- `WAN interface` = `ether1`
- `LAN gateway / CIDR` = `10.10.10.1/24`
- `DHCP pool start` = `10.10.10.10`
- `DHCP pool end` = `10.10.10.250`
- `HotSpot files directory` = `flash/esn-hotspot-hq`
- `Provider templates` = `clickpesa`
- `Create DNS static record` = `ON`
- `Attempt Let's Encrypt` = `OFF`

For `HotSpot DNS name`, choose one of these based on your reality:

- NAT/local deployment: `login.hq.wifi.local`
- router has public DNS + certificate plan: `login.hq.skywifibill.spotbox.online`

---

## 15. Final launch notes

Before calling the system fully live:

- deploy the VPS and confirm the public portal works
- rebuild web with the production `NEXT_PUBLIC_API_URL`
- confirm API health and web health publicly
- confirm ClickPesa credentials with the real API key
- ask ClickPesa whether they require source-IP whitelisting
- if yes, whitelist the VPS IP `139.84.240.120`
- onboard one real router first and test end-to-end on a phone

Related docs:

- [README.md](/Users/eunice/MY/esn-wifi-billing/README.md)
- [apps/web/docs/STAGING.md](/Users/eunice/MY/esn-wifi-billing/apps/web/docs/STAGING.md)
- [docs/RELEASE_CANDIDATE.md](/Users/eunice/MY/esn-wifi-billing/docs/RELEASE_CANDIDATE.md)
- [docs/UAT_CHECKLIST.md](/Users/eunice/MY/esn-wifi-billing/docs/UAT_CHECKLIST.md)
- [services/api/docs/BACKEND_ROLLOUT.md](/Users/eunice/MY/esn-wifi-billing/services/api/docs/BACKEND_ROLLOUT.md)

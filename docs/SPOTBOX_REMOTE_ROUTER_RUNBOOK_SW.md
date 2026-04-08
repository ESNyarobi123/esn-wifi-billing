# ESN Spotbox Runbook: VPS hadi Router ya MikroTik

Mwongozo huu umeandaliwa kutokana na hatua tulizofanikiwa kweli kwenye production setup ya `skywifibill.spotbox.online`. Lengo lake ni kukuachia kumbukumbu ya uhakika ya:

- ku-run mfumo kwenye VPS
- kuunganisha router ya mbali ambayo haipo same network na VPS
- kutumia WireGuard kati ya VPS na MikroTik
- ku-add router kwenye ESN web
- kujaza `Generate router provisioning package`
- ku-prepare router kabla ya `Push to router`
- ku-troubleshoot makosa tuliyokutana nayo

## 1. Taarifa za production zilizothibitishwa

- Domain ya mfumo: `https://skywifibill.spotbox.online`
- VPS public IP: `139.84.240.120`
- Repo kwenye VPS: `/root/esn-wifi-billing`
- Reverse proxy: `Caddy`
- Web + API zipo kwenye domain moja:
  - Web: `https://skywifibill.spotbox.online/`
  - API: `https://skywifibill.spotbox.online/api/v1/...`
- Public API origin ya frontend:
  - `NEXT_PUBLIC_API_URL=https://skywifibill.spotbox.online`

## 2. Jambo la kwanza kuelewa kuhusu router ya mbali

Kama router yuko kwenye location nyingine au private LAN tofauti, VPS haiwezi kumfikia kwa IP ya ndani kama:

- `192.168.88.1`
- `10.0.0.1`
- `172.16.x.x`

Dalili yake kwenye ESN web:

- `Test connection` huonyesha `offline`

Suluhisho la salama na la kudumu:

- tumia `WireGuard` kati ya VPS na MikroTik
- ESN itumie **WireGuard IP** ya router, si IP ya LAN ya ndani

Mpango uliothibitishwa:

- VPS WG IP: `10.200.0.1/24`
- Router WG IP: `10.200.0.2/24`
- WireGuard UDP port: `51820`

Baada ya tunnel kuwaka:

- router host kwenye ESN = `10.200.0.2`

## 3. Hatua za VPS kwa WireGuard

### 3.1 Install packages

```bash
apt update
apt install -y wireguard qrencode
```

### 3.2 Generate keys

```bash
umask 077
wg genkey | tee /etc/wireguard/esn-vps.key | wg pubkey > /etc/wireguard/esn-vps.pub
cat /etc/wireguard/esn-vps.pub
```

### 3.3 Unda config ya WireGuard

Tengeneza faili:

`/etc/wireguard/wg-esn.conf`

Kabla ya kupata public key ya router, tumia interface-only:

```ini
[Interface]
Address = 10.200.0.1/24
ListenPort = 51820
PrivateKey = WEKA_PRIVATE_KEY_YA_/etc/wireguard/esn-vps.key
```

Kisha:

```bash
chmod 600 /etc/wireguard/wg-esn.conf
systemctl enable wg-quick@wg-esn
systemctl restart wg-quick@wg-esn
wg show
ip addr show wg-esn
```

Kitu cha kuthibitisha:

- interface `wg-esn` ipo
- ina `10.200.0.1/24`

### 3.4 Fungua UDP port kwenye firewall ya VPS

Kama unatumia UFW:

```bash
ufw allow 51820/udp
```

## 4. Hatua za MikroTik kwa WireGuard

### 4.1 Unda interface na IP

```rsc
/interface wireguard
add name=wg-esn listen-port=51820

/ip address
add address=10.200.0.2/24 interface=wg-esn comment="ESN WireGuard"
```

### 4.2 Pata public key ya router

```rsc
/interface wireguard print detail where name="wg-esn"
```

Chukua `public-key` ya router, kisha rudi VPS na ongeza `[Peer]` kwenye `/etc/wireguard/wg-esn.conf`:

```ini
[Interface]
Address = 10.200.0.1/24
ListenPort = 51820
PrivateKey = WEKA_PRIVATE_KEY_YA_VPS

[Peer]
PublicKey = WEKA_PUBLIC_KEY_YA_ROUTER
AllowedIPs = 10.200.0.2/32
PersistentKeepalive = 25
```

Kisha restart:

```bash
chmod 600 /etc/wireguard/wg-esn.conf
systemctl restart wg-quick@wg-esn
wg show
```

### 4.3 Ongeza peer ya VPS kwenye MikroTik

Tumia public key ya VPS:

```rsc
/interface wireguard peers
add interface=wg-esn public-key="WEKA_VPS_PUBLIC_KEY" allowed-address=10.200.0.1/32 endpoint-address=139.84.240.120 endpoint-port=51820 persistent-keepalive=25s
```

### 4.4 Ruhusu traffic ya WireGuard kwenye router

```rsc
/ip firewall filter
add action=accept chain=input protocol=udp dst-port=51820 comment="allow WireGuard UDP"
add action=accept chain=input src-address=10.200.0.0/24 comment="allow ESN WireGuard management"
```

Optional ya wazi zaidi kwa test ya management:

```rsc
/ip firewall filter
add action=accept chain=input protocol=tcp src-address=10.200.0.0/24 dst-port=21,8728,8729 comment="allow ESN TCP mgmt over WireGuard"
```

Weka rule hizi juu kabla ya drop rules:

```rsc
/ip firewall filter move [find where comment="allow WireGuard UDP"] 0
/ip firewall filter move [find where comment="allow ESN WireGuard management"] 1
/ip firewall filter move [find where comment="allow ESN TCP mgmt over WireGuard"] 2
```

## 5. Fungua API na FTP ya router kupitia WireGuard

Kwa test ya kwanza, tumia plain API:

```rsc
/ip service set api disabled=no port=8728 address=""
/ip service set api-ssl disabled=yes
/ip service set ftp disabled=no port=21 address=""
```

Baada ya kuthibitisha kila kitu kinafanya kazi, unaweza kuharden:

```rsc
/ip service set api address=10.200.0.0/24
/ip service set ftp address=10.200.0.0/24
```

Au kama unatumia TLS API:

```rsc
/ip service set api disabled=yes
/ip service set api-ssl disabled=no port=8729 address=10.200.0.0/24
/ip service set ftp address=10.200.0.0/24
```

## 6. Verify tunnel na ports

### 6.1 Kwenye VPS

```bash
wg show
ping -c 3 10.200.0.2
nc -vz -w 3 10.200.0.2 8728
nc -vz -w 3 10.200.0.2 21
```

Tunachotaka kuona:

- handshake ipo
- `ping` inafaulu
- `8728` inasema `succeeded`
- `21` inasema `succeeded`

### 6.2 Kwenye MikroTik

```rsc
/interface wireguard peers print detail
/ping 10.200.0.1
/ip service print detail where name~"api|api-ssl|ftp"
```

## 7. Jinsi ya ku-add router kwenye ESN web

Baada ya WireGuard kuwaka:

- `Host` = `10.200.0.2`
- `API port` = `8728`
- `TLS` = `OFF` kama unatumia plain API
- `Username` = admin wa kweli wa router
- `Password` = password ya kweli ya router

Kisha:

1. save
2. `Test connection`

Tunachotaka kuona:

- router awe `online`

## 8. Router mpya: prepare kwanza kabla ya Push to router

Kama utaweka `HotSpot interface = bridge-hotspot`, basi hiyo interface lazima iwepo kabla ya `Push to router`.

### 8.1 Prep ya bridge-hotspot

Kwa mfano kama hotspot utatumia `wlan1`:

```rsc
:if ([:len [/interface bridge find where name="bridge-hotspot"]] = 0) do={/interface bridge add name="bridge-hotspot" comment="ESN hotspot bridge"}
/interface bridge port remove [find where interface="wlan1"]
:if ([:len [/interface bridge port find where bridge="bridge-hotspot" and interface="wlan1"]] = 0) do={/interface bridge port add bridge="bridge-hotspot" interface="wlan1"}
/interface wireless set [find where name="wlan1"] mode=ap-bridge ssid="YOUR HOTSPOT SSID" disabled=no
```

### 8.2 Verify prep

```rsc
/interface bridge print
/interface bridge port print where bridge="bridge-hotspot"
/interface wireless print where name="wlan1"
```

## 9. Jinsi ya kujaza `Generate router provisioning package`

Kwa production setup yako ya Spotbox, jaza hivi:

- `Portal base URL` = `https://skywifibill.spotbox.online`
- `API base URL` = `https://skywifibill.spotbox.online`
- `HotSpot interface` = `bridge-hotspot`
- `WAN interface` = `ether1`
- `LAN gateway / CIDR` = `10.10.10.1/24`
- `HotSpot DNS name` = `login.hq.wifi.local`
- `DHCP pool start` = `10.10.10.10`
- `DHCP pool end` = `10.10.10.250`
- `HotSpot files directory` = `flash/esn-hotspot-hq`
- `SSL certificate name` = acha blank kwa sasa
- `Extra walled-garden hosts` = acha blank kama huna host nyingine maalum
- `Provider templates` = `clickpesa`
- `Create DNS static record` = `ON`
- `Attempt Let’s Encrypt` = `OFF`

Maana ya msingi:

- `Portal base URL` na `API base URL` sasa ni za live domain, si LAN IP
- `HotSpot DNS name` ni hostname ya captive portal ya router, si lazima iwe sawa na domain ya VPS
- `bridge-hotspot` ni salama kuliko kutumia `bridge` ya kawaida iliyo na DHCP ya live

## 10. `Download zip` vs `Push to router`

### `Download zip`

Tumia hii kama:

- ni router wa kwanza
- hujaamini interface names
- unataka review script kabla ya import

### `Push to router`

Tumia hii kama:

- router API na FTP vinafikiwa
- `bridge-hotspot` ipo tayari
- credentials za router ni sahihi
- hotspot interface na WAN interface ziko sahihi

## 11. Kosa tulilokutana nalo: interface haipo

Error:

```text
Provisioning push failed: Script Error: input does not match any value of interface
```

Maana yake:

- uliweka `HotSpot interface = bridge-hotspot`
- lakini `bridge-hotspot` haikuwepo bado kwenye router

Suluhisho:

- create `bridge-hotspot` kwanza
- attach `wlan1` au interface ya guest humo
- kisha rudia `Push to router`

## 12. Kosa tulilokutana nalo: captive popup lakini `ERR_CONNECTION_REFUSED`

Sababu kubwa zilizowahi kutokea:

- portal ilikuwa bado inatumia `localhost` au LAN IP isiyofikika
- router hakuwa na walled-garden ya IP kwa host ya portal

Kilichofanya kazi:

- kutumia `Portal base URL` ya kweli inayofikika
- kuweka walled-garden host na walled-garden IP kwa portal host

## 13. Baada ya Push to router, verify hizi

```rsc
/ip hotspot print
/ip hotspot profile print
/ip dns static print
/file print where name~"esn-hotspot"
```

Tunachotaka kuona:

- hotspot server ipo
- hotspot profile ipo
- DNS static ipo
- hotspot files zipo

## 14. Test ya simu baada ya push

1. connect kwenye SSID ya hotspot
2. hakikisha simu imepata IP ya `10.10.10.x`
3. kama popup haiji, fungua `http://neverssl.com`
4. hakikisha captive portal ya ESN inafunguka
5. chagua plan
6. jaribu flow ya payment au voucher

Command za kusaidia:

```rsc
/ip dhcp-server lease print where address~"10.10.10."
/ip hotspot host print
/ip hotspot active print
/ip hotspot walled-garden print
/ip hotspot walled-garden ip print
```

## 15. Maana ya `No whitelist entries`

Hii si error.

Maana yake tu:

- hakuna MAC iliyoongezwa kwenye whitelist bado

Kwa hiyo message:

```text
No whitelist entries.
```

ni taarifa ya kawaida, si kushindwa kwa provisioning.

## 16. ClickPesa note muhimu

Hali ya sasa ya live payment:

- provider wa mfumo ni `clickpesa`
- lakini kama portal ikirudisha `provider http 403`, shida ni auth ya ClickPesa

Angalia:

- `CLICKPESA_CLIENT_ID`
- `CLICKPESA_API_KEY`
- `CLICKPESA_CHECKSUM_KEY`
- IP whitelist upande wa ClickPesa

Kwa VPS hii, waambie ClickPesa wa-whitelist:

- `139.84.240.120`

## 17. Checklist ya mwisho ya router mpya

Fuata hii order:

1. hakikisha VPS iko live
2. hakikisha WireGuard kati ya VPS na router iko live
3. hakikisha `8728` na `21` zinafikiwa kutoka VPS kwenda router
4. add router kwenye ESN kwa `10.200.0.2`
5. `Test connection`
6. prepare `bridge-hotspot`
7. jaza `Generate router provisioning package`
8. `Push to router`
9. verify `/ip hotspot print`
10. test kwa simu

## 18. Kumbuka hizi ukirudi baadaye

- `NEXT_PUBLIC_API_URL` ikibadilika, lazima rebuild `web`
- baada ya backend release, run migrations
- usiweke router host ya production kama `192.168.x.x` ikiwa router yuko mbali; tumia WireGuard IP
- usi-push provisioning kwenye `bridge` ya kawaida bila kuelewa setup ya router
- badili password ya default ya admin wa seed mara moja

## 19. Faili zinazohusiana ndani ya project

- [docs/installtion on vps.md](/Users/eunice/MY/esn-wifi-billing/docs/installtion%20on%20vps.md)
- [docs/VPS_PRODUCTION_AND_ROUTER_ONBOARDING.md](/Users/eunice/MY/esn-wifi-billing/docs/VPS_PRODUCTION_AND_ROUTER_ONBOARDING.md)
- [README.md](/Users/eunice/MY/esn-wifi-billing/README.md)


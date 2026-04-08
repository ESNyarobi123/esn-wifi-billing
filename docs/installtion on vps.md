1. Mradi na mahali ulipo
Repo: ESNyarobi123/esn-wifi-billing
Kifungu cha kod kwenye sava: /root/esn-wifi-billing
Mfumo mwingine wa Docker (MNNFbot) ulikuwa tayari; haunguswi — hutumia mtandao tofauti na haja ya mifuko 80/443.
Msingi wa monorepo: Next.js (web), FastAPI (api) na Celery (worker + beat), PostgreSQL, Redis, kisha kwenye uzinduzi wa Spotbox: Caddy (HTTPS) na pgAdmin.

2. Huduma za Docker (nini hufanya kazi)
Huduma	Kazi
postgres
PostgreSQL 16, DATABASE esn_wifi
redis
Broker / cache kwa Celery na rate limits
api
FastAPI + Uvicorn, njia /api/v1/..., /docs, /health, nk.
worker
Celery worker
beat
Celery beat (kazi za ratiba)
web
Next.js standalone, UI ya admin + portal
caddy
Reverse proxy + HTTPS (Let’s Encrypt) kwenye mlango 80 na 443
pgadmin
UI ya kusimamia PostgreSQL (nyuma ya /pgadmin/)
3. Domain na HTTPS
Domain: skywifibill.spotbox.online (DNS inaelekeza kwenye IP ya VPS).
Caddy hushughulikia cheti la TLS moja kwa moja (ACME).
Faili ya usanidi: infra/spotbox/Caddyfile.
Urambazaji (moja kwa moja):

Web (Next): https://skywifibill.spotbox.online/ → kontena web:3000
API (kivinjari): https://skywifibill.spotbox.online/api/v1/... (msingi sawa na domain — hakuna subdomain tofauti ya API)
Nyaraka: https://skywifibill.spotbox.online/docs, /openapi.json, nk.
pgAdmin: https://skywifibill.spotbox.online/pgadmin/ (URL kamili na / mwishoni inapendekezwa)
4. Faili maalum zilizoundwa / kurekebishwa
Kitu	Maana
infra/spotbox/Caddyfile
Mipangilio ya Caddy (gzip, security headers, routing)
docker-compose.spotbox.yml
Inajumuisha docker-compose.yml, kuongeza Caddy + pgAdmin, na marekebisho kwa web/api (URL ya uzinduzi, CORS ya production)
docker-compose.yml
Imeimarishwa: NEXT_PUBLIC_API_URL inatoka ${NEXT_PUBLIC_API_URL} kutoka .env; baadhi ya ports zimefunikwa kwenye 127.0.0.1 (Postgres, Redis, API, Web) ili mtandao wa nje uingie hasa kupitia Caddy
.env (mizizi ya mradi)
Mazingira yote muhimu (DB, JWT, ClickPesa, MikroTik, NEXT_PUBLIC_API_URL, pgAdmin, nk.)
Amri ya uzinduzi:

cd /root/esn-wifi-billing
docker compose -f docker-compose.yml -f docker-compose.spotbox.yml up -d --build
5. Mazingira (.env) — muhimu
POSTGRES_* na DATABASE_URL — hutumika na API na Docker.
JWT_SECRET_KEY — siri ya JWT (imeimarishwa kutoka “change-me” kwa matumizi ya umma).
ROUTER_CREDENTIALS_FERNET_KEY — muhimu kwa kusimba nywila za router kwenye DB.
NEXT_PUBLIC_API_URL=https://skywifibill.spotbox.online — asili ambayo kivinjari kinatumia kwa API (hakuna / mwishoni); inachomekwa wakati wa build ya Next.
CORS_ORIGINS — imejumuisha domain ya HTTPS pamoja na LAN/localhost kwa mahitaji ya maabara.
docker-compose.spotbox.yml bado inaweza kuweka CORS_ORIGINS ya API kwa uzinduzi moja (https://skywifibill.spotbox.online) — hakikisha inalingana na ukweli wa matumizi.
ClickPesa / MikroTik — sawa na maadili uliyoweka (malipo halisi, mock imezimwa kama ulivyoweka).
PGADMIN_DEFAULT_EMAIL / PGADMIN_DEFAULT_PASSWORD — kuingia pgAdmin pekee; huletiwi env_file nzima ya monorepo ndani ya kontena ya pgAdmin (kulinda import config ya pgAdmin kutokana na mabadiliko kama API_PORT).
PGADMIN_LISTEN_ADDRESS=0.0.0.0 iko katika Spotbox compose ili IPv4 na Docker ziendane.
Siri zote za kweli ziko kwenye /root/esn-wifi-billing/.env — usizisambazi.

6. Usalama (ufupi)
API, web, Postgres na Redis kwa kawaida sio wazi kwa umma moja kwa moja; zimefungwa kwenye 127.0.0.1 (debug/kutumia SSH tunnel inawezekana).
Mlango wa mtandao wa kawaida kwa wateja: 80 na 443 (Caddy).
PGADMIN na API bado zina nywila za kuingia — bora badili nywila za default mara moja kwenye mfumo na .env unapoweza.
7. Databesi: migrations na seed
Hapo awali data haikuwepo (hakuna majedwali).
Kisha ilifanywa: alembic upgrade head (migrations hadi 004_payment_callback_dedupe).
Kisha: python -m app.seed na SEED_DEMO_DATA=false — RBAC, admin, site hq, bila seti kamili ya maonyesho.
Kuingia dashboard ya wavuti:
admin@esn.local / nenosiri default ya seed: ChangeMe123! (badilisha mara ya kwanza ukiingia).

pgAdmin: barua pepe + PGADMIN_DEFAULT_PASSWORD kutoka .env.
PostgreSQL kutoka pgAdmin: host postgres, port 5432, POSTGRES_USER / POSTGRES_PASSWORD kutoka .env.

8. Mambo ya kukumbuka baadaye
Baada ya badiliko la NEXT_PUBLIC_API_URL, lazima docker compose ... build web (au --build) ili bundle ya JS ianze upya.
Baada ya release mpya ya backend: alembic upgrade head kwenye DB ya uzinduzi.
SEED_DEMO_DATA=true ni kwa demo pekee (si bora ukiwa na data halisi tayari).
Hifadhi backup ya PostgreSQL (volume esn-wifi-billing_postgres-data) na .env salama.
9. Muhtasari wa hatua zilizopigwa (mlolongo)
Kukloni repo na kuunda mfumo wa Docker + Spotbox (Caddy + pgAdmin).
Kuweka HTTPS na routing ya domain moja (web + API + pgAdmin).
Kuimarisha .env, kusawazisha Postgres password, kusasisha NEXT_PUBLIC_API_URL na docker-compose.yml kuitumia.
Kuangalia na kuendesha migrations na minimal seed.
Kutoa maelezo ya kuingia pgAdmin, Postgres, na dashboard.
Kama unataka, naweza kuandika runbook mpendwa (copy-paste) kwa: deploy, backup DB, na rollback ya image — lakini hilo lingehitaji faili mpya ya nyaraka au maelekezo tu unayoyaomba.
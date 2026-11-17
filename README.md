# The Daily Scroll v3: GitHub Pages

1. Maak op GitHub een nieuwe **public** repository genaamd `the-daily-scroll`, met branch `main`.
2. Upload de **inhoud** van deze map naar de root van de repository, niet de map `daily-scroll-site` zelf. Vereist: `index.html`, `data/articles.json`, `scripts/update_feed.py`, `.github/workflows/daily.yml` en optioneel `README.md`. De `.github`-map is een verborgen map: controleer dat die effectief is meegekomen; als upload via browser dit niet doet, maak `.github/workflows/daily.yml` aan via 'Add file → Create new file'.
3. Bij **Settings → Pages → Build and deployment** kies je **Source: GitHub Actions** (niet 'Deploy from a branch').
4. Bij **Settings → Actions → General → Workflow permissions** kies je 'Read and write permissions' als GitHub dat vereist en toelaat. De workflow heeft schrijfrecht nodig om `data/articles.json` te bewaren.
5. Bij **Actions → Daily Scroll refresh and publish → Run workflow** kun je onmiddellijk de eerste volledige update en publicatie starten. Een upload op `main` kan ook al een run triggeren.
6. Bij **Settings → Pages** verschijnt na een geslaagde deployment een `Visit site`-link; doorgaans `https://GEBRUIKERSNAAM.github.io/the-daily-scroll/`.

## Werking

- Publicatie van de webapp en RSS-updates gebeuren in **dezelfde workflow**, zodat ook wijzigingen door een GitHub Action op de website komen. Let op: GitHub start geplande acties niet gegarandeerd exact op tijd.
- De planning probeert op werkdagen 06:15 Europe/Brussels uit te voeren; een zomertijd-/wintertijdcontrole in het script slaat de tweede UTC-run over.
- Nieuwe berichten worden regelgebaseerd uit RSS-feeds gekozen, niet AI-gecureerd. Links en publicatiedata komen uit RSS en kunnen onjuist/onvolledig zijn. Oude kaarten worden bewaard; er is nog geen koppeling met de ChatGPT-briefing.
- Bewaard/gelezen wordt lokaal per browser opgeslagen. Publiceer geen vertrouwelijke informatie: de Pages-site is publiek.


## v5: Nederlandse samenvattingen, afbeeldingen en bronmedia

Klik op een artikelkaart om eerst een Nederlandstalige introductie te lezen. Met **Lees bij de bron** ga je pas naar de uitgever. Een aantal startartikelen heeft een gecontroleerde, handmatig geschreven samenvatting op basis van het volledige bronartikel. De herkomst staat bij elke samenvatting.

De dagelijkse GitHub Action voert `scripts/enrich_articles.py` uit en zoekt een bronafbeelding (Open Graph), videolinks en een korte bronbeschrijving. Afbeeldingen worden rechtstreeks bij de uitgever geladen; als een uitgever dat blokkeert blijft de themakaart zichtbaar. De melding over video of afbeeldingen is gebaseerd op automatisch aangetroffen paginametadata, en kan onvolledig zijn. Gebruik de oorspronkelijke bron voor alle media.

### Optionele automatische AI-samenvattingen

Zonder extra configuratie maakt de geplande updater **geen nieuwe AI-samenvattingen**. Dan toont de app bij nieuwe artikelen eerlijk een korte uitleg uit de titel en bronsamenvatting. Voor automatische Nederlandse samenvattingen van nieuwe artikelen moet je zelf een **OpenAI API-sleutel** beschikbaar maken:

1. Maak apart een API-sleutel aan via het OpenAI API-platform en controleer eerst de bijbehorende gebruikskosten. Een ChatGPT-abonnement bevat niet automatisch API-tegoed.
2. GitHub repository → **Settings → Secrets and variables → Actions → New repository secret**.
3. Naam: `OPENAI_API_KEY`. Waarde: jouw sleutel. Plak deze **nooit** in HTML, een commit of `articles.json`.
4. Start onder **Actions** opnieuw de workflow.

De AI krijgt momenteel uitsluitend de korte bronbeschrijving en titel, **niet het volledige artikel**. Dit is bewust, wegens beschikbaarheid, toegang en auteursrechten. Zulke stukken krijgen in de app het label *op basis van de bronbeschrijving*. De automatische resultaten zijn geen door een redacteur gecontroleerde samenvattingen van de hele publicatie. De handmatig nagelezen startartikelen worden niet overschreven.

De automatische AI-stap is optioneel en kan API-kosten veroorzaken. Ook bij ingeschakelde AI blijft factchecking belangrijk.

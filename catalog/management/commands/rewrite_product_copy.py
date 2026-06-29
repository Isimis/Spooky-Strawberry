"""Pełne przepisanie opisów produktów (curated copy).

Treść jest pisana ręcznie w brand-voice Spooky Strawberry (PL), pod SEO i GEO:
dłuższe, naturalne opisy, gęste sensownymi słowami kluczowymi. Zasada redakcyjna:
nie nazywamy stylu wprost „alternatywnym" — opisujemy konkretny klimat
(goth, grunge, dark coquette, jirai kei, e-girl, Y2K) zamiast krzyczeć etykietą.

Komenda jest idempotentna: aktualizuje pola description / styling_tips /
seo_description / seo_title dla produktów dopasowanych po `slug`.

Użycie:
    python manage.py rewrite_product_copy            # zastosuj zmiany
    python manage.py rewrite_product_copy --dry-run  # tylko pokaż, nic nie zapisuj
"""

from django.core.management.base import BaseCommand

from catalog.models import Product


# slug -> nowa treść. Zachowane fakty produktowe (materiały, konstrukcja,
# kolory) zgodne z dotychczasowymi danymi — niczego nie zmyślamy.
PRODUCT_COPY = {
    "gotycki-skorzany-choker-z-krzyzami-silver-star": {
        "seo_title": "Skórzany Choker z Krzyżami „Silver Star” – Gotycka Obroża",
        "seo_description": (
            "Cienki choker z eko-skóry z metalowymi krzyżami i gwiazdami oraz "
            "regulowanym łańcuszkiem. Lekka, wygodna obroża, która domyka "
            "mroczne i romantyczne stylizacje."
        ),
        "styling_tips": (
            "Noś solo do głębszych dekoltów albo warstwowo z dłuższymi srebrnymi "
            "naszyjnikami i delikatną koronką. Pasuje zarówno do miękkich, "
            "romantycznych looków w klimacie dark coquette, jak i do "
            "mocniejszych zestawów z ciężkimi butami i skórą."
        ),
        "description": (
            "Subtelny mrok, który nosisz dokładnie tak mocno, jak masz ochotę. "
            "Choker „Silver Star” to idealny kompromis między ciężką, surową "
            "estetyką a delikatnym, romantycznym dark coquette — cienki, "
            "elegancki pasek przylega do szyi, nie przytłaczając sylwetki, a "
            "drobne metalowe krzyże i gwiazdy łapią światło i przyciągają "
            "spojrzenia przy każdym ruchu.\n"
            "Obroża została wykonana z miękkiej skóry ekologicznej, dzięki czemu "
            "jest przyjemna w dotyku i wygodna w noszeniu przez cały dzień — od "
            "porannych zajęć po wieczorne wyjście. Materiał nie obciera i "
            "układa się płasko pod kołnierzykiem koszuli czy ramiączkiem topu.\n"
            "Z tyłu znajdziesz klasyczne zapięcie z łańcuszkiem przedłużającym, "
            "które pozwala dopasować obwód do siebie w kilka sekund i nosić "
            "choker ciaśniej lub luźniej, zależnie od nastroju i reszty "
            "stylizacji.\n"
            "Najlepiej wygląda noszony solo do głębszych dekoltów albo "
            "warstwowo z dłuższymi, srebrnymi naszyjnikami — zbuduj z niego "
            "wielopoziomową kompozycję, która robi cały klimat outfitu. To "
            "dodatek, po który będziesz sięgać codziennie, a który w sekundę "
            "podnosi nawet najprostszy zestaw."
        ),
    },
    "gotyckie-podwiazki-z-sercem-heartbreaker": {
        "seo_title": "Gotyckie Podwiązki na Udo z Sercem „Heartbreaker”",
        "seo_description": (
            "Podwiązki na udo z eko-skóry z regulowanymi paskami i metalowymi "
            "żabkami na zakolanówki i pończochy. Mroczny pazur i uroczy detal w "
            "kształcie serca w jednym."
        ),
        "styling_tips": (
            "Zestaw z krótką spódniczką, zakolanówkami lub pończochami i "
            "masywnymi butami. Świetnie wyglądają wyeksponowane na gołym udzie "
            "albo nałożone na kryjące rajstopy — jako odważny, rockowy akcent z "
            "nutą gotyckiego romantyzmu."
        ),
        "description": (
            "Mroczny pazur i uroczy detal w jednym. Podwiązki „Heartbreaker” "
            "przełamują spokojne, klasyczne stylizacje, dodając im odważnego, "
            "rockowego charakteru z odrobiną gotyckiego romantyzmu — to ten "
            "element, który sprawia, że prosty zestaw zaczyna opowiadać "
            "historię.\n"
            "Zaprojektowane nie tylko po to, żeby świetnie wyglądać, ale też być "
            "maksymalnie funkcjonalne. Wykonane z solidnej skóry ekologicznej "
            "(PU) mają regulowane paski, więc dopasujesz je do każdego obwodu "
            "uda — zarówno na gołą nogę, jak i na rajstopy czy legginsy.\n"
            "Mocne, metalowe żabki utrzymają Twoje ulubione zakolanówki czy "
            "pończochy dokładnie tam, gdzie mają być, i nie pozwolą im się "
            "zsuwać podczas chodzenia, tańca czy całego dnia na nogach. Detal w "
            "kształcie serca dodaje całości charakterystycznego, dziewczęcego "
            "akcentu.\n"
            "Zestaw je z krótką spódniczką, masywnymi butami i mocniejszym "
            "makijażem oczu — i ruszaj w miasto. To dodatek, który robi z "
            "outfitu statement bez potrzeby kompletowania całej nowej szafy."
        ),
    },
    "dlugie-pasiaste-mitenki-grunge-icon": {
        "seo_title": "Długie Pasiaste Mitenki / Ocieplacze na Ręce „Grunge Icon”",
        "seo_description": (
            "Długie pasiaste ocieplacze na ręce z miękkiej, elastycznej "
            "dzianiny, z wycięciem na kciuk. Mroczna nostalgia lat 2000 w "
            "klimacie grunge, e-girl i Y2K."
        ),
        "styling_tips": (
            "Najprostszy sposób, by oversize'owy t-shirt z zespołem albo top na "
            "ramiączkach zamienić w przemyślany look. Warstwuj je na koncerty, "
            "spacery i chłodniejsze dni w klimacie grunge, e-girl i Y2K."
        ),
        "description": (
            "Mroczna nostalgia lat 2000 w jednym dodatku. Długie, pasiaste "
            "ocieplacze na ręce to detal, którego trudno nie zauważyć — "
            "najprostszy i najbardziej efektowny sposób, by zwykły, oversize'owy "
            "t-shirt z zespołem czy prosty top na ramiączkach zamienić w "
            "kompletną, przemyślaną stylizację w klimacie grunge, e-girl lub "
            "Y2K.\n"
            "Mitenki uszyto z miękkiej, elastycznej dzianiny, która przyjemnie "
            "ogrzewa ręce, ale daje pełną swobodę ruchów i nie krępuje "
            "nadgarstków. Materiał dobrze się układa i nie zsuwa się w dół "
            "przedramienia w trakcie noszenia.\n"
            "Dzięki specjalnemu wycięciu na kciuk ocieplacze trzymają się "
            "stabilnie na dłoni i pozwalają wygodnie scrollować telefon, pisać "
            "na klawiaturze czy trzymać kubek z kawą — bez ściągania.\n"
            "Idealne na chłodniejsze dni, koncerty, jesienne spacery i do "
            "budowania warstwowych (layered) outfitów. To niedrogi sposób, by "
            "dodać stylizacji charakteru i od razu poczuć klimat lat 2000."
        ),
    },
    "gotyckie-koronkowe-mankiety-z-kokarda-maidcore": {
        "seo_title": "Koronkowe Mankiety z Kokardą „Maidcore” – Gotycki Detal",
        "seo_description": (
            "Warstwowe koronkowe mankiety z satynową kokardką i wszytą "
            "elastyczną gumką. Drobny detal w stylu gothic lolita i dark "
            "coquette, który podnosi całą stylizację."
        ),
        "styling_tips": (
            "Noś na nadgarstkach jako urozmaicenie krótkiego rękawa albo nałóż "
            "na mankiety prostej koszuli dla wiktoriańskiego klimatu. Świetnie "
            "grają w stylizacjach dark coquette, jirai kei i gothic lolita."
        ),
        "description": (
            "Mały detal, który robi gigantyczną różnicę. Koronkowe mankiety to "
            "esencja estetyki gothic lolita i dark coquette — to właśnie takie "
            "drobne akcesoria sprawiają, że cały outfit staje się "
            "wielowymiarowy, dopracowany i przyciąga wzrok.\n"
            "Wykonane z kilku warstw miękkiej, marszczonej koronki i zwieńczone "
            "uroczą, satynową kokardką, dodają stylizacji romantycznej, lekko "
            "teatralnej głębi. Każda warstwa pracuje przy ruchu ręki, tworząc "
            "delikatny, falujący efekt.\n"
            "Wszyta, elastyczna gumka idealnie dopasowuje mankiety do "
            "nadgarstka — trzymają się pewnie, ale nie uciskają, więc możesz "
            "nosić je przez cały dzień bez dyskomfortu.\n"
            "Możesz nosić je na nadgarstkach jako urozmaicenie krótkiego rękawa "
            "albo nałożyć na mankiety prostej koszuli, nadając jej "
            "wiktoriańskiego, mrocznego klimatu. To niepozorny dodatek, który "
            "potrafi całkowicie odmienić wymowę zestawu."
        ),
    },
    "rajstopy-imitujace-zakolanowki-kawaii-neko": {
        "seo_title": "Rajstopy Imitujące Zakolanówki „Kawaii Neko” z Kotkami",
        "seo_description": (
            "Rajstopy z iluzją czarnych zakolanówek i cielistą górą — nie "
            "zsuwają się przez cały dzień. Kocie uszka z przodu i ogony z tyłu. "
            "Słodki, kawaii detal do mini spódniczek."
        ),
        "styling_tips": (
            "Perfekcyjne do spódniczek mini, sukienek w stylu lolita i szortów. "
            "Łącz z butami Mary Jane i platformami w klimacie dark coquette, "
            "e-girl i jirai kei, gdy chcesz dodać stylizacji uroczego pazura."
        ),
        "description": (
            "Efekt zakolanówek bez ich ciągłego zsuwania. Rajstopy „Kawaii "
            "Neko” to sprytne połączenie wygody i uroczej estetyki — dają "
            "iluzję klasycznych, czarnych zakolanówek, ale dzięki cielistej, "
            "przezroczystej górze trzymają się idealnie na miejscu przez cały "
            "dzień. Koniec z poprawianiem zsuwającego się materiału co kilka "
            "kroków.\n"
            "Największym atutem jest jednak wzór: z przodu, tuż nad kolanami, "
            "wystają urocze kocie uszka z pyszczkiem, a z tyłu wiją się długie "
            "kocie ogony. To detal, który zauważają inni i o który najczęściej "
            "pytają.\n"
            "Materiał jest elastyczny i dobrze dopasowuje się do nogi, a "
            "kontrast czerni i koloru skóry optycznie wysmukla sylwetkę i "
            "wydłuża nogi.\n"
            "To perfekcyjny wybór do spódniczek mini, sukienek w stylu lolita i "
            "szortów — detal, który sprawi, że Twoja słodko-mroczna stylizacja "
            "naprawdę przyciągnie spojrzenia."
        ),
    },
    "wzorzyste-rajstopy-kabaretki-kitty-core": {
        "seo_title": "Wzorzyste Rajstopy Kabaretki „Kitty Core” z Kotkiem",
        "seo_description": (
            "Kabaretki z wplecionym motywem kociej twarzy. Z daleka klasyczna "
            "siateczka, z bliska słodki detal w klimacie Sanrio i jirai kei. "
            "Mroczny vibe spotyka totalny urok."
        ),
        "styling_tips": (
            "Genialne do plisowanych spódniczek, sukienek w kratę i butów Mary "
            "Jane na grubej podeszwie. Przełamują ciężki, gotycki look odrobiną "
            "japońskiego, kawaii klimatu."
        ),
        "description": (
            "Mroczny vibe spotyka totalny urok. Rajstopy „Kitty Core” to idealny "
            "sposób na przełamanie klasycznej, ciężkiej stylizacji goth czy "
            "grunge odrobiną japońskiego klimatu kawaii — bez rezygnowania z "
            "mrocznego charakteru.\n"
            "Zamiast zwykłej, jednolitej siateczki te kabaretki mają wpleciony "
            "kultowy motyw z twarzą kotka. Z daleka wyglądają jak klasyczne, "
            "czarne rajstopy we wzory, a z bliska zdradzają Twoje zamiłowanie do "
            "estetyki Sanrio i jirai kei — to taki mały sekret dla tych, którzy "
            "przyjrzą się bliżej.\n"
            "Elastyczna siateczka dobrze układa się na nodze i dodaje "
            "stylizacji tekstury oraz głębi, jednocześnie optycznie wydłużając "
            "sylwetkę.\n"
            "Genialnie wyglądają w zestawieniu z plisowanymi spódniczkami, "
            "sukienkami w kratę i butami typu Mary Jane na grubej podeszwie. To "
            "ten detal, który zamienia poprawny outfit w zapamiętywany."
        ),
    },
    "gotyckie-ponczochy-kabaretki-z-podwiazka-dark-lolita": {
        "seo_title": "Gotyckie Pończochy Kabaretki z Podwiązką „Dark Lolita”",
        "seo_description": (
            "Pończochy kabaretki ze zintegrowaną koronką, krzyżującymi się "
            "paskami i satynowymi kokardkami. Gotowy efekt „wow” bez osobnego "
            "pasa do pończoch."
        ),
        "styling_tips": (
            "Obowiązkowe do krótkich spódniczek, sukienek w stylu JK i masywnych "
            "butów na platformie. Dodają gotyckiego pazura, zachowując "
            "dziewczęcy urok — dark coquette, goth i jirai kei w jednym."
        ),
        "description": (
            "Mroczny urok i wygoda w jednym. Te pończochy to absolutny "
            "game-changer dla fanek wielowarstwowych stylizacji — zamiast męczyć "
            "się z osobnym pasem do pończoch, dostajesz gotowy, zintegrowany "
            "element, który od razu robi cały efekt „wow”.\n"
            "Klasyczna, drobna siateczka (kabaretka) łączy się tu z elastyczną, "
            "marszczoną koronką na udzie, która delikatnie obejmuje nogę i nie "
            "wbija się w skórę. Całość dopełniają krzyżujące się paski i urocze, "
            "satynowe kokardki, które nadają pończochom charakterystyczny, "
            "gotycko-dziewczęcy sznyt.\n"
            "Konstrukcja jest przemyślana tak, by trzymać się stabilnie przez "
            "cały dzień i wieczór, bez ciągłego podciągania — zakładasz i "
            "zapominasz.\n"
            "To obowiązkowy dodatek do krótkich spódniczek, sukienek w stylu JK "
            "i masywnych butów na platformie. Dodają mocnego, gotyckiego "
            "charakteru, zachowując przy tym dziewczęcy urok — idealne, gdy "
            "chcesz wyglądać groźnie i słodko jednocześnie."
        ),
    },
    "koronkowe-podkolanowki-z-wiazaniem-dark-romance": {
        "seo_title": "Koronkowe Podkolanówki z Wiązaniem „Dark Romance”",
        "seo_description": (
            "Podkolanówki z kwiatowej koronki z długimi tasiemkami do wiązania "
            "kokard pod kolanem. Dostępne w czerni i bieli — zmysłowa koronka i "
            "baletowy mrok."
        ),
        "styling_tips": (
            "Krzyżuj i wiąż tasiemki w kokardy tuż pod kolanem. Perfekcyjne do "
            "Mary Jane, platform i krótkich spódniczek. Czerń buduje klasyczny "
            "mrok, biel rozjaśnia i przełamuje look w stylu jirai kei."
        ),
        "description": (
            "Zmysłowa koronka i baletowy mrok. Podkolanówki „Dark Romance” to "
            "detal, który całkowicie zmienia proporcje i charakter Twojej "
            "stylizacji — przyciągają wzrok do nóg i dodają zestawowi "
            "romantycznej, lekko teatralnej nuty.\n"
            "Wykonane z elastycznej, kwiatowej koronki, miękko dopasowują się "
            "do łydki i nie zsuwają się w dół. Wzór koronki pięknie prześwituje "
            "i nadaje nodze delikatnej, wiktoriańskiej tekstury.\n"
            "Największą robotę robią tu jednak długie tasiemki — możesz je "
            "dowolnie krzyżować i wiązać w urocze kokardy tuż pod kolanem, za "
            "każdym razem trochę inaczej, dopasowując efekt do nastroju.\n"
            "To perfekcyjny wybór do masywnych butów typu Mary Jane, platform i "
            "krótkich spódniczek. Wybierz czerń dla klasycznego, mrocznego looku "
            "albo biel, by rozjaśnić i przełamać cięższą stylizację w stylu "
            "jirai kei. Sprawdzą się i na co dzień, i na wieczorne wyjście."
        ),
    },
    "czarne-podarte-rajstopy-kabaretki-grunge-core": {
        "seo_title": "Czarne Podarte Rajstopy Kabaretki „Grunge Core”",
        "seo_description": (
            "Podarte kabaretki z asymetrycznymi, fabrycznymi dziurami, które "
            "nie prują się dalej. Surowa estetyka i maksymalny pazur w klimacie "
            "grunge i goth."
        ),
        "styling_tips": (
            "Warstwuj na kryjące rajstopy w chłodne dni albo noś solo na "
            "koncerty. Idealna baza pod ciężkie platformy, spódniczki mini i "
            "oversize'owe t-shirty z zespołami."
        ),
        "description": (
            "Surowa estetyka i maksymalny pazur. Jeśli Twoja szafa opiera się na "
            "ciężkich butach na platformie, spódniczkach mini i oversize'owych "
            "t-shirtach z zespołami, podarte kabaretki „Grunge Core” to "
            "brakujący element, który spina cały ten klimat w całość.\n"
            "Asymetryczne, fabrycznie wykonane dziury nadają rajstopom mocnego, "
            "zniszczonego charakteru (distressed look) — bez ryzyka, że materiał "
            "rozejdzie się dalej w trakcie noszenia. Każda para układa się "
            "trochę inaczej, więc Twój look jest naprawdę jeden jedyny.\n"
            "Elastyczna siateczka dobrze trzyma się na nodze i pozwala "
            "swobodnie się ruszać — na koncercie, w mieście i na imprezie.\n"
            "Idealne do budowania warstw: świetnie wyglądają nałożone na zwykłe, "
            "kryjące rajstopy w chłodniejsze dni albo noszone solo, gdy chcesz "
            "postawić na surowy, zbuntowany efekt. To tani sposób, by dodać "
            "stylizacji pazura i charakteru."
        ),
    },
    "gotyckie-spinki-do-wlosow-vampire-tears-zestaw-2-szt": {
        "seo_title": "Gotyckie Spinki do Włosów „Vampire Tears” (Zestaw 2 szt.)",
        "seo_description": (
            "Zestaw 2 gotyckich spinek do symetrycznych, warstwowych upięć. "
            "Dostępne w czerni i wampirycznym burgundzie — detal, który domyka "
            "całą fryzurę i stylizację."
        ),
        "styling_tips": (
            "Wepnij po bokach głowy, przy kucykach albo jako ozdobę grzywki. "
            "Czerń zgra się z każdym mrocznym outfitem, burgund doda "
            "wiktoriańskiego, wampirycznego akcentu."
        ),
        "description": (
            "Detal, który domyka całą fryzurę. Zestaw dwóch gotyckich spinek to "
            "absolutna podstawa przy tworzeniu symetrycznych, warstwowych upięć "
            "w stylu dark coquette, gothic lolita czy jirai kei — bo to właśnie "
            "włosy często decydują o tym, czy cała stylizacja gra.\n"
            "Spinki świetnie sprawdzają się wpięte po bokach głowy, przy "
            "kucykach, kosmykach przy twarzy albo jako ozdoba grzywki. Dzięki "
            "temu, że dostajesz dwie sztuki, łatwo zbudujesz symetryczny, "
            "dopracowany efekt z obu stron.\n"
            "Mocowanie pewnie trzyma kosmyki na miejscu, więc upięcie "
            "wytrzymuje cały dzień — od porannych zajęć po wieczorne wyjście.\n"
            "Głęboka czerń to klasyka, która zgra się z każdym mrocznym "
            "outfitem, natomiast odcień czerwonego wina (burgund) dodaje "
            "stylizacji mocnego, wampirycznego, wiktoriańskiego akcentu. To "
            "drobiazg, który robi nieproporcjonalnie duże wrażenie."
        ),
    },
    "koronkowe-mitenki-z-falbanka-i-kokarda-dollhouse": {
        "seo_title": "Koronkowe Mitenki bez Palców z Falbanką i Kokardą „Dollhouse”",
        "seo_description": (
            "Koronkowe rękawiczki bez palców z marszczoną falbanką i "
            "miniaturową kokardką. Warstwowy, romantyczny detal w stylu dark "
            "coquette i jirai kei."
        ),
        "styling_tips": (
            "Noś do krótkich rękawów albo jako przedłużenie mrocznych, "
            "gotyckich koszul. Konstrukcja bez palców pozwala swobodnie "
            "korzystać z telefonu — dark coquette, jirai kei, gothic lolita, Y2K."
        ),
        "description": (
            "Detal, który przenosi stylizację na zupełnie inny poziom. "
            "Koronkowe rękawiczki bez palców to jeden z najbardziej "
            "charakterystycznych elementów estetyki dark coquette i jirai kei — "
            "romantyczny, lekko gotycki akcent, który od razu nadaje całości "
            "klimatu.\n"
            "Siateczkowy materiał, mocno marszczona falbanka wokół nadgarstka i "
            "urocza, miniaturowa kokardka tworzą idealny, warstwowy efekt. "
            "Mitenki świetnie wyglądają zarówno do krótkich rękawów, jak i jako "
            "subtelne przedłużenie mrocznych, gotyckich koszul.\n"
            "Konstrukcja bez palców (fingerless) pozwala swobodnie korzystać z "
            "telefonu, pisać i trzymać kubek, jednocześnie zachowując pełen "
            "klimat stylizacji — wygoda i estetyka idą tu w parze.\n"
            "To niepozorny dodatek, który zamienia prostą bazę w przemyślany, "
            "dziewczęco-mroczny look. Świetnie wypada też w duecie z koronkowymi "
            "mankietami czy chokerem z tej samej półki."
        ),
    },
    "prazkowane-skarpetki-z-falbanka-doll": {
        "seo_title": "Prążkowane Skarpetki z Falbanką „Doll”",
        "seo_description": (
            "Prążkowane skarpetki z delikatną, marszczoną falbanką u góry. "
            "Dostępne w czerni i bieli — stworzone do butów Mary Jane i "
            "masywnych platform."
        ),
        "styling_tips": (
            "Idealne do Mary Jane i platform. Czerń sprawdzi się w cięższych "
            "stylizacjach, biel doda dziewczęcego kontrastu — dark coquette, "
            "jirai kei, gothic lolita."
        ),
        "description": (
            "Stworzone do Twoich ulubionych butów Mary Jane i masywnych "
            "platform. Prążkowane skarpetki „Doll” to absolutna podstawa "
            "stylizacji dark coquette i jirai kei — niby drobiazg, a robią całą "
            "robotę przy odsłoniętej kostce i łydce.\n"
            "Delikatna, marszczona falbanka na samej górze dodaje dziewczęcego "
            "uroku i przełamuje surowość ciężkich butów, a klasyczna faktura "
            "prążka sprawia, że skarpetki ładnie układają się na nodze i dobrze "
            "się trzymają.\n"
            "Miękki, elastyczny splot jest przyjemny w noszeniu na co dzień — do "
            "szkoły, na uczelnię, na spacer i na wieczór.\n"
            "Wybierz mroczną czerń do cięższych stylizacji albo niewinną biel, "
            "by stworzyć idealny, dziewczęcy kontrast z masywnym obuwiem. To "
            "tani sposób, by domknąć look od stóp i nadać mu charakteru."
        ),
    },
    "koronkowe-skarpetki-z-falbanka-obsession": {
        "seo_title": "Koronkowe Skarpetki z Falbanką „Obsession”",
        "seo_description": (
            "Koronkowe skarpetki z delikatną falbanką, które przełamują surowy "
            "look dziewczęcym akcentem. Dostępne w czerni i bieli — must-have "
            "mrocznej, romantycznej szafy."
        ),
        "styling_tips": (
            "Noś do ciężkich platform, klasycznych Mary Jane albo mokasynów. "
            "Czerń buduje klasyczny dark coquette, biel daje mocny kontrast w "
            "stylu jirai kei."
        ),
        "description": (
            "Detal, który spaja całą estetykę. Niezależnie od tego, czy "
            "wybierasz ciężkie platformy, klasyczne Mary Jane, czy mokasyny — "
            "koronkowe skarpetki „Obsession” to absolutny must-have, który "
            "przełamuje surowy look delikatnym, dziewczęcym akcentem przy "
            "kostce.\n"
            "Subtelna koronka z marszczoną falbanką u góry dodaje stylizacji "
            "lekkości i romantyzmu, a elastyczny splot sprawia, że skarpetki "
            "dobrze trzymają się na nodze i nie zsuwają się w trakcie noszenia.\n"
            "To wdzięczny, uniwersalny dodatek na co dzień i na wyjście, który "
            "pasuje do spódniczek, sukienek i szortów — zawsze dokładając "
            "stylizacji ten brakujący, dopracowany szczegół.\n"
            "Wybierz głęboką czerń dla klasycznego dark coquette albo czystą "
            "biel, by stworzyć mocny, dziewczęcy kontrast w stylu jirai kei. "
            "Świetnie grają w duecie z koronkowymi podkolanówkami z tej samej "
            "kolekcji."
        ),
    },
}


class Command(BaseCommand):
    help = "Pełne przepisanie opisów produktów (curated copy) dla katalogu."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Pokaż, co zostałoby zmienione, ale nic nie zapisuj.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        missing = []

        for slug, copy in PRODUCT_COPY.items():
            product = Product.objects.filter(slug=slug).first()
            if product is None:
                missing.append(slug)
                continue

            for field, value in copy.items():
                setattr(product, field, value)

            if not dry_run:
                product.save(update_fields=list(copy.keys()) + ["updated_at"])
            updated += 1
            self.stdout.write(f"{'[dry-run] ' if dry_run else ''}OK: {product.name}")

        for slug in missing:
            self.stdout.write(self.style.WARNING(f"Brak produktu o slug: {slug}"))

        verb = "Do zmiany" if dry_run else "Zaktualizowano"
        self.stdout.write(self.style.SUCCESS(f"{verb}: {updated} produktów."))

# Spooky Strawberry - pelna checklista migracji i rozwoju

Ten dokument jest robocza mapa projektu Spooky Strawberry w Django. Ma pomagac prowadzic prace etapami: najpierw przeniesienie zawartosci i klimatu obecnej strony Shopify, potem ulepszenia katalogu, koszyka, analityki, customowego panelu administracyjnego i pozniejszych funkcji AI.

Checkout, platnosci PayU/Przelewy24 i finalne procesowanie zamowien sa celowo odlozone do czasu, az bedzie gotowa dzialalnosc gospodarcza i decyzje formalno-prawne.

## Legenda priorytetow

- `P0` - fundament albo blokada dla dalszych prac.
- `P1` - wazne dla dobrego UX, migracji ze starej strony albo startu sklepu.
- `P2` - ulepszenie, automatyzacja albo funkcja pozniejsza.

## Zrodla porownania

- Obecna strona glowna Shopify: https://www.spookystrawberry.pl/
- Obecny katalog Shopify: https://www.spookystrawberry.pl/collections/all
- Obecna strona kontaktu Shopify: https://www.spookystrawberry.pl/pages/contact
- Publiczny katalog produktow Shopify: https://www.spookystrawberry.pl/products.json?limit=250

## Aktualny snapshot Shopify

- [x] `P0` Obecny publiczny katalog Shopify zawiera 13 produktow.
- [x] `P0` Obecny publiczny katalog Shopify zawiera 17 wariantow.
- [x] `P0` Obecny publiczny katalog Shopify zawiera 62 zdjecia produktowe.
- [x] `P0` Obecna strona ma announcement bar z komunikatem o darmowej dostawie od 50 zl.
- [x] `P0` Obecna strona ma header z linkami: Strona glowna, Katalog, Kontakt.
- [x] `P0` Obecna strona ma wyszukiwanie.
- [x] `P0` Obecna strona ma konto klienta jako element nawigacji.
- [x] `P0` Obecna strona ma koszyk/drawer koszyka z pustym stanem.
- [x] `P0` Obecna strona glowna pokazuje sekcje "Nasz najnowszy drop".
- [x] `P0` Obecna strona glowna pokazuje grid produktow z przyciskami "Dodaj" i "Wybierz".
- [x] `P0` Obecna strona ma globalny newsletter.
- [x] `P0` Obecna stopka ma linki do polityk i informacji prawnych.
- [x] `P0` Obecna strona kontaktu ma formularz kontaktowy.

## Najblizsze kroki

- [ ] `P0` Dopracowac desktopowy wyglad strony glownej: hero, spacing, produkt promowany, grid produktow, newsletter i stopke.
- [ ] `P0` Dopracowac desktopowy wyglad katalogu: sidebar filtrow, karty produktow, szerokosc siatki i aktywne filtry.
- [ ] `P0` Dopracowac desktopowy wyglad karty produktu: galeria, sticky panel zakupu, warianty, opis, szczegoly i podobne produkty.
- [ ] `P0` Uporzadkowac tresci polityk jako robocze placeholdery, z jasna informacja, ze wymagaja finalizacji przed sprzedaza.
- [ ] `P1` Rozbudowac model tresci strony glownej tak, aby sekcje home nie byly zaszyte na sztywno w template.
- [x] `P1` Przygotowac prosty koszyk sesyjny bez checkoutu i bez platnosci.
- [x] `P1` Zaczac lekka analityke zdarzen: page view, product view, search, filter applied, add to cart.
- [ ] `P1` Spisac osobna liste rzeczy do sprawdzenia wizualnie na mobile, gdy bedzie dostep do podgladu telefonu.

## 0. Aktualny stan projektu

- [x] `P0` Projekt Django dziala lokalnie.
- [x] `P0` Repozytorium jest prowadzone w Git.
- [x] `P0` Istnieja aplikacje: `core`, `catalog`, `cart`, `checkout`, `orders`, `outfits`, `blog`, `accounts`, `dashboard`, `ai_tools`.
- [x] `P0` Skonfigurowano globalne `templates`, `static`, `media`.
- [x] `P0` Skonfigurowano `.env` i `.env.example`.
- [x] `P0` Ustawiono jezyk `pl` i strefe czasu `Europe/Warsaw`.
- [x] `P0` Importer Shopify pobiera aktualne produkty, warianty, tagi, ceny i zdjecia.
- [x] `P0` Modele katalogu obsluguja produkty, warianty, kategorie, estetyki, kolory, rozmiary i zdjecia.
- [x] `P0` Istnieje widok `/sklep/`.
- [x] `P0` Istnieje widok `/produkt/<slug>/`.
- [x] `P0` Istnieja placeholdery: kontakt, wyszukiwanie, koszyk, konto, polityki.
- [x] `P0` Istnieja pierwsze modele domenowe dla kont, stylizacji, bloga, zamowien, checkout draft, dashboardu, AI i tresci core.
- [ ] `P0` Uporzadkowac obecne zmiany w Git i zrobic commit bazowy po zakonczeniu tego etapu.
- [ ] `P1` Dodac minimalne testy regresji dla home, katalogu, produktu, kontaktu, wyszukiwania, koszyka i polityk.
- [ ] `P1` Dodac dokument "jak odpalic projekt lokalnie" dla przyszlego siebie.
- [ ] `P2` Rozdzielic settings na lokalne/produkcyjne dopiero wtedy, gdy projekt bedzie blizej deployu.

## 1. Migracja zawartosci z Shopify

- [x] `P0` Pobrac z Shopify 13 produktow.
- [x] `P0` Pobrac z Shopify 17 wariantow.
- [x] `P0` Pobrac z Shopify 62 zdjecia.
- [x] `P0` Pobrac tytuly produktow.
- [x] `P0` Pobrac ceny produktow.
- [x] `P0` Pobrac slugi/handle produktow.
- [x] `P0` Pobrac tagi produktow i zmapowac je na estetyki.
- [x] `P0` Pobrac opisy HTML i przerobic je na tekst do pol Django.
- [ ] `P0` Porownac kazdy opis produktu w Django z oryginalem Shopify i poprawic formatowanie recznie tam, gdzie importer splycil tresc.
- [ ] `P0` Przeniesc `seo_title` i `seo_description` z Shopify dokladniej, nie tylko z nazwy i pierwszego zdania.
- [ ] `P0` Sprawdzic, czy wszystkie glowne zdjecia produktow zgadzaja sie z Shopify.
- [ ] `P0` Sprawdzic, czy kolejnosc zdjec w galerii produktu zgadza sie z Shopify.
- [ ] `P0` Sprawdzic warianty kolorystyczne produktow z wieloma kolorami: spinki, mitenki, skarpetki.
- [ ] `P0` Poprawic nazwy wariantow, aby byly naturalne po polsku i zgodne z aktualnym sklepem.
- [ ] `P1` Dodac pole na oryginalny Shopify product id dla latwiejszego syncu.
- [ ] `P1` Dodac pole na oryginalny Shopify variant id dla latwiejszego syncu.
- [ ] `P1` Dodac pole na oryginalny URL produktu.
- [ ] `P1` Dodac pole na zrodlo importu i date ostatniej synchronizacji.
- [ ] `P1` Ustalic, czy importer Shopify zostaje narzedziem roboczym, czy bedzie usuniety po pelnej migracji.
- [ ] `P1` Przeniesc tresci stron informacyjnych: polityka prywatnosci, polityka zwrotow, warunki uslug, polityka wysylki, dane kontaktowe, nota prawna, preferencje cookie.
- [ ] `P1` Przeniesc tresci meta/OG z Shopify: title, description, og:image, product metadata.
- [ ] `P1` Sprawdzic favicon i podstawowe brand assets ze starej strony.
- [ ] `P2` Przygotowac mechanizm ponownego importu, ktory nie nadpisuje recznych poprawek opisow.
- [ ] `P2` Przygotowac raport roznic miedzy Shopify i Django: brakujace produkty, inne ceny, inne zdjecia, inne warianty.

## 2. Strona glowna

- [ ] `P0` Dopasowac desktopowy hero do obecnego klimatu Shopify.
- [ ] `P0` Ustalic finalna tresc hero po polsku: bez infantylnego tonu, ale cute, mrocznie i dziewczeco.
- [ ] `P0` Pokazac w hero realny produkt albo realne zdjecie z aktualnego dropu.
- [ ] `P0` Dodac sekcje "Przedstawiamy" jako odpowiednik Shopify.
- [ ] `P0` Dopasowac sekcje "Nasz najnowszy drop" do obecnej strony.
- [ ] `P0` Pokazac wszystkie produkty nowego dropu albo kontrolowana liczbe z przyciskiem "Wyswietl wszystko".
- [ ] `P1` Dodac sekcje polecanych produktow.
- [x] `P1` Dodac sekcje gotowych stylizacji jako placeholder do czasu modeli `outfits`.
- [ ] `P1` Dodac sekcje kolekcji/estetyk: Soft goth, Dark coquette, Jirai kei, Grunge, Y2K/emo.
- [ ] `P1` Dodac sekcje poradnikowa SEO z linkami do przyszlych artykulow.
- [ ] `P1` Dodac newsletter z tekstem inspirowanym Shopify: nowe dropy i promocje.
- [ ] `P1` Dodac przyciski CTA: "Zobacz katalog", "Nowy drop", "Znajdz swoj klimat".
- [ ] `P1` Zadbac o desktopowy rhythm: marginesy, szerokosci, proporcje zdjec.
- [ ] `P1` Zadbac o mobile-first wersje strony glownej po zatwierdzeniu desktopu.
- [ ] `P2` Zrobic model/konfiguracje sekcji home, aby admin mogl sterowac kolejnoscia produktow i tekstami.
- [ ] `P2` Dodac testy widoku home: produkty aktywne, brak produktow, linki do katalogu i produktu.

## 3. Katalog produktow

- [x] `P0` Dodac route `/sklep/`.
- [x] `P0` Pokazywac produkty aktywne.
- [x] `P0` Dodac podstawowe filtry: kategoria, estetyka, kolor, rozmiar, cena, dostepnosc.
- [x] `P0` Dodac sortowanie.
- [x] `P0` Dodac aktywne filtry jako chipsy.
- [x] `P0` Dodac swatche kolorow na kartach produktow.
- [ ] `P0` Dopasowac desktopowy katalog do Shopify: szerokosci, grid, wyglad filtracji, produkt cards.
- [ ] `P0` Poprawic karty produktow: zdjecie, hover, tytul, cena, status, CTA.
- [x] `P0` Dodac realny stan pusty dla braku wynikow.
- [x] `P0` Dodac wyswietlanie liczby wynikow i aktualnego sortowania w estetyczny sposob.
- [ ] `P1` Dodac filtrowanie przez linki w sekcjach estetyk na home.
- [ ] `P1` Dodac opcje "Wyswietl wszystko" z sekcji home.
- [ ] `P1` Dodac szybki podglad produktu albo szybkie dodanie do koszyka pozniej, po koszyku sesyjnym.
- [x] `P1` Dodac paginacje albo lazy loading, zanim katalog urosnie.
- [ ] `P1` Dodac filtr "nowy drop".
- [ ] `P1` Dodac filtr "polecane".
- [ ] `P1` Dodac filtr po typie akcesorium bardziej biznesowo niz obecne heurystyki importera.
- [ ] `P1` Dodac czytelne URL-e filtrow dla SEO i udostepniania.
- [ ] `P2` Dodac sortowanie po popularnosci, gdy analityka zacznie zbierac dane.
- [ ] `P2` Dodac rekomendacje "czesto ogladane" w katalogu.
- [x] `P2` Dodac testy filtrow i sortowania.

## 4. Karta produktu

- [x] `P0` Dodac route `/produkt/<slug>/`.
- [x] `P0` Pokazac galerie zdjec.
- [x] `P0` Pokazac nazwe, cene, kategorie, estetyki.
- [x] `P0` Pokazac warianty i dostepnosc.
- [x] `P0` Pokazac opis klimatyczny.
- [x] `P0` Pokazac szczegoly produktu.
- [x] `P0` Pokazac wskazowki stylizacyjne.
- [x] `P0` Dodac podobne produkty z tej samej kategorii.
- [ ] `P0` Dopasowac desktopowy layout karty produktu do Shopify.
- [ ] `P0` Upewnic sie, ze pierwsze zdjecie produktu jest dobrze kadrowane.
- [ ] `P0` Zrobic galerie z miniaturami albo przewijaniem, zalezne od finalnego designu.
- [ ] `P0` Ulepszyc wybor wariantu: kolor jako swatch, rozmiar jako przycisk, stan wybrany.
- [x] `P0` Zablokowac przycisk dodawania do koszyka, jesli wariant niedostepny.
- [ ] `P1` Dodac realna obsluge ilosci po stronie JS.
- [ ] `P1` Dodac sekcje "Dostawa i zwroty" jako accordion.
- [ ] `P1` Dodac sekcje "Materialy i pielegnacja", jesli dane beda dostepne.
- [x] `P1` Dodac powiazane gotowe stylizacje.
- [ ] `P1` Dodac podobne produkty po estetyce, nie tylko po kategorii.
- [ ] `P1` Dodac meta tagi produktu: title, description, OG, product price, image.
- [ ] `P1` Dodac JSON-LD Product schema.
- [ ] `P2` Dodac rekomendacje oparte o analityke: ogladane razem, dodawane razem, kupowane razem.
- [ ] `P2` Dodac testy: produkt aktywny, produkt draft, warianty, brak zdjec, podobne produkty.

## 5. Gotowe stylizacje

- [x] `P0` Ustalic minimalny model `Outfit`: nazwa, slug, opis, estetyki, glowne zdjecie, status.
- [x] `P0` Ustalic model produktow w zestawie: outfit, produkt/wariant, ilosc, sort_order.
- [x] `P1` Dodac liste gotowych stylizacji.
- [x] `P1` Dodac szczegoly stylizacji.
- [x] `P1` Pokazac zdjecie/modelke/outfit.
- [x] `P1` Pokazac produkty w zestawie.
- [x] `P1` Pokazac cene osobno.
- [x] `P1` Pokazac cene zestawu.
- [ ] `P1` Dodac CTA "Dodaj caly zestaw" dopiero po koszyku sesyjnym.
- [x] `P1` Dodac linki do pojedynczych produktow.
- [x] `P1` Powiazac stylizacje z karta produktu.
- [ ] `P1` Powiazac stylizacje z poradnikami SEO.
- [ ] `P2` Dodac rabaty zestawowe.
- [ ] `P2` Dodac analityke skutecznosci stylizacji: views, clicks, add_to_cart, conversion.

## 6. Poradniki SEO

- [x] `P0` Ustalic minimalny model artykulu: title, slug, intro, body, status, published_at, SEO fields.
- [x] `P1` Dodac liste poradnikow.
- [x] `P1` Dodac widok artykulu.
- [x] `P1` Powiazac artykuly z produktami.
- [x] `P1` Powiazac artykuly z gotowymi stylizacjami.
- [ ] `P1` Dodac sekcje poradnikowa na home.
- [x] `P1` Dodac sekcje produktow pod artykulem.
- [ ] `P1` Dodac linkowanie z produktu do poradnika.
- [ ] `P1` Przygotowac tematy SEO: dark coquette, jirai kei, gotyckie dodatki, rajstopy alt, chokery, mitenki, skarpetki z falbanka.
- [ ] `P2` Dodac AI jako pomoc w szkicach artykulow, ale nie publikowac bez recznej korekty.
- [ ] `P2` Dodac statystyki: artykul -> klikniecia produktow -> dodania do koszyka -> zakup w przyszlosci.

## 7. Koszyk bez checkoutu

- [x] `P0` Zrobic koszyk sesyjny bez platnosci i bez checkoutu.
- [x] `P0` Dodac dodawanie wariantu produktu do koszyka.
- [x] `P0` Dodac zmiane ilosci.
- [x] `P0` Dodac usuwanie pozycji.
- [x] `P0` Dodac pusty stan koszyka jak w Shopify.
- [x] `P0` Dodac podsumowanie cen pozycji.
- [ ] `P1` Dodac drawer koszyka albo osobna strone koszyka zgodna z obecnym Shopify.
- [x] `P1` Dodac komunikat "checkout bedzie dostepny pozniej" tylko lokalnie/roboczo.
- [x] `P1` Dodac walidacje stocku.
- [x] `P1` Dodac obsluge wariantow kolorystycznych.
- [ ] `P1` Dodac kod rabatowy jako placeholder bez realnego naliczania albo odlozyc do pozniej.
- [ ] `P1` Dodac dostawke jako placeholder bez finalnych stawek.
- [ ] `P2` Dodac porzucony koszyk do analityki.
- [x] `P2` Dodac testy koszyka sesyjnego.

## 8. Konto klienta

- [ ] `P1` Zostawic konto jako placeholder do czasu zamowien.
- [ ] `P1` Ustalic, czy konto bedzie wymagane, czy zakupy beda mozliwe jako gosc.
- [ ] `P1` Dodac logowanie/rejestracje dopiero po decyzji o zamowieniach.
- [ ] `P1` Docelowo pokazac historie zamowien.
- [ ] `P1` Docelowo pokazac dane klienta.
- [ ] `P1` Docelowo dodac ulubione produkty.
- [ ] `P2` Docelowo dodac preferencje estetyk klientki.
- [ ] `P2` Docelowo wykorzystac preferencje do rekomendacji produktow.

## 9. Custom admin/dashboard

- [x] `P0` Nie rozbudowywac domyslnego Django Admin jako glownego narzedzia.
- [x] `P0` Zaprojektowac customowy panel administracyjny w aplikacji `dashboard`.
- [x] `P1` Dodac dashboard z podstawowym podsumowaniem: produkty, warianty, brakujace dane, ostatnie zmiany.
- [x] `P1` Dodac liste produktow w custom dashboard.
- [x] `P1` Dodac edycje produktu.
- [x] `P1` Dodac edycje wariantow.
- [x] `P1` Dodac zarzadzanie zdjeciami.
- [x] `P1` Dodac zarzadzanie kategoriami i estetykami.
- [x] `P1` Dodac zarzadzanie gotowymi stylizacjami.
- [x] `P1` Dodac zarzadzanie artykulami SEO.
- [ ] `P1` Dodac ekran importu/synchronizacji z Shopify jako narzedzie robocze.
- [x] `P1` Dodac walidator brakow produktu: brak SEO, brak zdjec, brak wariantow, brak opisu.
- [ ] `P2` Dodac role/uzytkownikow panelu.
- [x] `P2` Docelowo ograniczyc albo usunac publiczne uzywanie domyslnego `/admin/`.

## 10. Analityka i sciezki uzytkownika

- [x] `P0` Zaprojektowac minimalna aplikacje `analytics`.
- [x] `P0` Ustalic model sesji uzytkownika: session_key, first_seen, last_seen, device, referrer, utm.
- [x] `P0` Ustalic model eventu: session, event_type, path, product, variant, metadata, created_at.
- [x] `P1` Rejestrowac `page_view`.
- [x] `P1` Rejestrowac `product_view`.
- [x] `P1` Rejestrowac `search`.
- [x] `P1` Rejestrowac `filter_applied`.
- [x] `P1` Rejestrowac `add_to_cart`.
- [x] `P1` Rejestrowac `cart_view`.
- [ ] `P1` Rejestrowac porzucenie koszyka w prosty sposob.
- [x] `P1` Zbierac podstawowe dane urzadzenia: mobile/desktop, przegladarka, system.
- [x] `P1` Zbierac zrodlo ruchu: referrer, utm_source, utm_campaign.
- [x] `P1` Przechowywac kolejnosc stron w sesji.
- [ ] `P1` Powiazac eventy z produktami, wariantami, kategoriami, estetykami i artykulami.
- [ ] `P2` Dodac dashboard analityczny: najczesciej ogladane produkty, porzucenia, sciezki, skuteczne zrodla ruchu.
- [ ] `P2` Dodac raport "co poprawic w UX".
- [ ] `P2` Dodac raport "jakie produkty dokupic".
- [ ] `P2` Dodac anonimizacje/retencje danych zgodna z przyszla polityka prywatnosci.

## 11. AI po stronie administracyjnej

- [ ] `P2` Nie implementowac AI przed stabilnym katalogiem, koszykiem, zamowieniami i analityka.
- [ ] `P2` Dodac AI assistant jako modul custom dashboard, nie jako element publicznego sklepu.
- [ ] `P2` Generowac szkice opisow produktow.
- [ ] `P2` Proponowac tagi i estetyki na podstawie nazwy/zdjec/opisu.
- [ ] `P2` Wykrywac brakujace dane produktu.
- [ ] `P2` Proponowac SEO title i SEO description.
- [ ] `P2` Proponowac podobne produkty i stylizacje.
- [ ] `P2` Analizowac statystyki i sugerowac produkty do dokupienia.
- [ ] `P2` Pomagac przy grafikach dopiero po ustaleniu realnego workflow.
- [ ] `P2` Wymagac recznej akceptacji kazdej tresci generowanej przez AI.

## 12. Design, mobile, desktop, performance

- [ ] `P0` Najpierw dopracowac desktop, bo aktualnie jest dostepny podglad PC.
- [ ] `P0` Potem wrocic do mobile-first i sprawdzic home, katalog, produkt, koszyk.
- [ ] `P0` Zachowac klimat obecnego Shopify: alternatywny, cute, lekko mroczny, dziewczecy, bez sztucznosci.
- [ ] `P0` Utrzymac komunikacje po polsku.
- [ ] `P0` Nie robic strony marketingowej zamiast sklepu - pierwszy ekran ma prowadzic do produktow.
- [ ] `P1` Uporzadkowac design tokens: kolory, typografia, spacing, promienie, cienie.
- [ ] `P1` Dopracowac header desktop.
- [ ] `P1` Dopracowac header mobile.
- [ ] `P1` Dopracowac stopke.
- [ ] `P1` Dopracowac karty produktow.
- [ ] `P1` Dopracowac formularze.
- [ ] `P1` Dopracowac stany hover/focus.
- [ ] `P1` Dopracowac stany puste.
- [ ] `P1` Dopracowac loading states tam, gdzie bedzie JS.
- [ ] `P1` Zoptymalizowac zdjecia produktow.
- [ ] `P1` Dodac `alt_text` lepszy niz sama nazwa produktu, jesli potrzebne dla SEO.
- [ ] `P1` Sprawdzic Lighthouse albo podobne narzedzie dopiero po ustabilizowaniu widokow.
- [ ] `P2` Dodac automatyczne generowanie miniaturek.
- [ ] `P2` Dodac WebP/AVIF lokalnie lub przez przyszly storage/CDN.

## 13. Rzeczy odlozone do czasu dzialalnosci

- [ ] `P0` Nie integrowac PayU przed gotowa dzialalnoscia.
- [ ] `P0` Nie integrowac Przelewy24 przed gotowa dzialalnoscia.
- [ ] `P0` Nie uruchamiac finalnego checkoutu przed decyzjami formalnymi.
- [ ] `P0` Nie publikowac finalnych polityk bez sprawdzenia prawnego.
- [ ] `P1` Przygotowac checkout jako projekt techniczny dopiero pozniej.
- [x] `P1` Przygotowac wstepny pasywny model zamowien bez checkoutu i bez integracji platnosci.
- [ ] `P1` Przygotowac integracje dostawy dopiero po decyzji o operatorach i stawkach.
- [ ] `P2` Przygotowac produkcyjny PostgreSQL dopiero blizej deployu.
- [ ] `P2` Przygotowac deployment, domeny, maile i monitoring dopiero blizej publikacji.

## Definicja gotowosci przed startem publicznym

- [ ] `P0` Wszystkie produkty z Shopify sa obecne w Django.
- [ ] `P0` Wszystkie produkty maja poprawne ceny, warianty, zdjecia, opisy i SEO.
- [ ] `P0` Home, katalog i produkt sa dopracowane na desktop.
- [ ] `P0` Home, katalog i produkt sa dopracowane na mobile.
- [ ] `P0` Koszyk dziala przynajmniej sesyjnie.
- [ ] `P0` Polityki i dane kontaktowe sa gotowe formalnie.
- [ ] `P0` Checkout i platnosci sa wdrozone dopiero po gotowosci dzialalnosci.
- [ ] `P1` Podstawowa analityka zbiera zdarzenia.
- [x] `P1` Custom dashboard pozwala zarzadzac katalogiem bez domyslnego Django Admin.
- [ ] `P1` Testy regresji pokrywaja glowne widoki i przeplywy.
- [ ] `P1` Strona laduje sie szybko i poprawnie pokazuje media.

## Notatki decyzyjne

- Checkout i platnosci sa poza biezacym zakresem.
- Domyslny Django Admin nie jest docelowym panelem pracy.
- Kod piszemy po angielsku, teksty sklepu po polsku.
- Projekt zostaje na Django Templates, CSS i prostym JavaScript, dopoki nie pojawi sie realna potrzeba Reacta/Next.js.
- Mobile-first pozostaje celem, ale aktualny najblizszy przeglad wizualny robimy na desktopie.
- Analityke projektujemy wczesnie, ale dashboard analityczny i AI dopiero po solidnym katalogu i koszyku.

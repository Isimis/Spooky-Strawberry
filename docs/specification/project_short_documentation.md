# Spooky Strawberry - krotka dokumentacja projektu

## Cel projektu

Spooky Strawberry to autorski sklep internetowy tworzony w Django jako docelowy zamiennik obecnej strony Shopify. Projekt ma przeniesc klimat marki: alternatywny, lekko mroczny, cute i dziewczecy, ale bez przesadnie infantylnego tonu. Strona jest projektowana mobile first, bo glowna grupa klientek bedzie korzystac przede wszystkim z telefonu.

Najwazniejszy cel techniczny to zbudowanie prostego, czytelnego i rozwijalnego e-commerce: katalog produktow, warianty, zdjecia, koszyk, zamowienia, checkout, konto klienta, panel administracyjny oraz analityka zachowan uzytkowniczek.

## Stack technologiczny

- Backend: Python, Django 5.2
- Widoki: Django Templates
- Frontend: CSS i podstawowy JavaScript
- Baza lokalna: SQLite
- Baza docelowa: prawdopodobnie PostgreSQL
- Media: lokalny katalog `media/`
- Statyczne zasoby: `static/`
- Konfiguracja srodowiska: `.env` i `python-dotenv`

## Glowna struktura aplikacji

- `core` - strona glowna, strony informacyjne, newsletter, wyszukiwarka, globalne ustawienia strony, szablony maili i komunikacja.
- `catalog` - katalog produktow, kategorie, estetyki, kolory, rozmiary, warianty, zdjecia produktow, lista produktow, karta produktu i quiz stylu.
- `outfits` - gotowe stylizacje, produkty w zestawie, zdjecia stylizacji i cena pakietowa.
- `cart` - koszyk sesyjny, trwaly koszyk dla zalogowanych uzytkownikow, dodawanie produktow i zestawow.
- `checkout` - dane dostawy, platnosc, tworzenie zamowienia i potwierdzenie.
- `orders` - modele zamowien, pozycji zamowien, metod dostawy i kodow rabatowych.
- `accounts` - rejestracja, logowanie, konto klienta, profil, adresy, ulubione produkty i weryfikacja e-mail.
- `blog` - poradniki SEO powiazane z produktami, stylizacjami i estetykami.
- `analytics` - sesje, zdarzenia, rozpoznawanie urzadzenia, UTM, referrer i podstawowe sledzenie sciezki.
- `dashboard` - wlasny panel administracyjny dla produktow, zamowien, newslettera, analityki, tresci i ustawien.
- `ai_tools` - fundament pod przyszle zadania AI, np. opisy produktow, SEO, tagi i analizy.

## Najwazniejsze modele

Katalog opiera sie na modelach `Product`, `ProductVariant`, `ProductImage`, `Category`, `Aesthetic`, `Color` i `Size`. Produkt moze miec status szkicu, aktywny albo archiwalny, cene regularna i promocyjna, oznaczenia typu polecany/nowosc/bestseller oraz ustawienia niskiego stanu magazynowego.

Stylizacje sa reprezentowane przez `Outfit`, `OutfitItem` i `OutfitImage`. Stylizacja moze laczyc kilka produktow, miec opis klimatu, porady stylizacyjne, powiazane estetyki i opcjonalna cene zestawu.

Zamowienia skladaja sie z `Order`, `OrderItem`, `ShippingMethod` i `DiscountCode`. Koszyk jest przechowywany w sesji, a dla zalogowanych klientek dodatkowo w modelu `SavedCart`.

Analityka zapisuje `AnalyticsSession` oraz `AnalyticsEvent`. Obecnie obslugiwane sa m.in. odslony stron, widoki produktow, wyszukiwanie, filtrowanie, dodanie do koszyka i widok koszyka.

## Glowny routing

- `/` - strona glowna
- `/sklep/` - lista produktow
- `/produkt/<slug>/` - karta produktu
- `/estetyki/` - lista estetyk
- `/estetyki/<slug>/` - produkty i tresci powiazane z estetyka
- `/quiz-stylu/` - quiz stylu
- `/stylizacje/` - lista gotowych stylizacji
- `/stylizacje/<slug>/` - szczegoly stylizacji
- `/poradniki/` - lista artykulow SEO
- `/poradniki/<slug>/` - artykul
- `/koszyk/` - koszyk
- `/zamowienie/dostawa/` - krok dostawy
- `/zamowienie/platnosc/` - krok platnosci
- `/zamowienie/potwierdzenie/<order_number>/` - potwierdzenie zamowienia
- `/konto/` - konto klienta
- `/admin/` - wlasny dashboard projektu
- `/django-admin/` - standardowy panel Django

## Uruchomienie lokalne

1. Utworz i aktywuj srodowisko wirtualne.
2. Zainstaluj zaleznosci:

```bash
pip install -r requirements.txt
```

3. Skopiuj konfiguracje srodowiska:

```bash
Copy-Item .env.example .env
```

4. Wykonaj migracje:

```bash
python manage.py migrate
```

5. Opcjonalnie zaladuj startowe tresci:

```bash
python manage.py seed_starter_content
```

6. Uruchom serwer:

```bash
python manage.py runserver
```

## Zasady dalszego rozwoju

- Projektujemy mobile first.
- Kod i nazwy techniczne trzymamy po angielsku.
- Tresci, komunikaty i dokumentacje robocze piszemy po polsku.
- Rozwiazania powinny byc proste, etapowe i zgodne z obecnym stylem Django Templates.
- React/Next.js nie sa potrzebne, dopoki nie pojawi sie realny powod.
- Najpierw rozwijamy solidny katalog, warianty, zdjecia, koszyk, zamowienia i analityke.
- AI zostaje jako etap pozniejszy, glownie dla panelu administracyjnego.

## Najblizsze sensowne kroki

- Dopracowanie modeli i widokow katalogu produktow.
- Uporzadkowanie checkoutu i finalizacji zamowienia.
- Rozbudowa dashboardu o wygodna prace na produktach, wariantach i zdjeciach.
- Doprecyzowanie analityki sciezki zakupowej.
- Ujednolicenie tresci i wygladu z aktualna marka Spooky Strawberry.
- Przygotowanie projektu pod pozniejsze wdrozenie produkcyjne.

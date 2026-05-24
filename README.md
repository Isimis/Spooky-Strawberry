# Spooky Strawberry Django

Custom e-commerce platform for Spooky Strawberry.

## Main modules

- Homepage
- Product catalog
- Product detail
- Product variants
- Ready-made outfits
- Cart
- Checkout
- Customer accounts
- SEO blog
- Custom admin dashboard
- AI assistant for product management

## Tech stack

- Python
- Django
- SQLite locally
- PostgreSQL in production
- Django Templates
- CSS
- JavaScript



Spooky Strawberry
│
├── Strona główna
│   ├── Hero / najnowszy drop
│   ├── Polecane produkty
│   ├── Gotowe kreacje
│   ├── Kolekcje / estetyki
│   │   ├── Soft goth
│   │   ├── Dark coquette
│   │   ├── Jirai kei
│   │   ├── Grunge
│   │   └── Y2K / emo
│   ├── Sekcja poradnikowa SEO
│   └── Newsletter
│
├── Sklep / katalog
│   ├── Lista produktów
│   ├── Filtrowanie
│   │   ├── Kolor
│   │   ├── Rozmiar
│   │   ├── Typ produktu
│   │   ├── Estetyka
│   │   ├── Cena
│   │   └── Dostępność
│   ├── Sortowanie
│   └── Szybkie dodanie do koszyka
│
├── Produkt
│   ├── Galeria zdjęć
│   ├── Nazwa
│   ├── Cena
│   ├── Warianty
│   │   ├── Kolor
│   │   └── Rozmiar
│   ├── Dodaj do koszyka
│   ├── Opis klimatyczny
│   ├── Szczegóły produktu
│   ├── Jak stylizować
│   ├── Powiązane kreacje
│   └── Podobne produkty
│
├── Gotowe kreacje
│   ├── Lista kreacji
│   └── Szczegóły kreacji
│       ├── Zdjęcie/modelka/outfit
│       ├── Produkty w zestawie
│       ├── Cena osobno
│       ├── Cena zestawu
│       ├── Dodaj cały zestaw
│       └── Wejdź w pojedyncze produkty
│
├── Poradniki
│   ├── Lista artykułów
│   └── Artykuł
│       ├── Treść SEO
│       ├── Produkty powiązane
│       └── Kreacje powiązane
│
├── Koszyk
│   ├── Produkty
│   ├── Zestawy
│   ├── Kod rabatowy
│   ├── Dostawa
│   └── Przejdź do płatności
│
├── Checkout
│   ├── Dane klienta
│   ├── Dostawa
│   ├── Płatność
│   └── Potwierdzenie
│
├── Konto klienta
│   ├── Zamówienia
│   ├── Dane
│   └── Ulubione
│
└── Panel administracyjny
    ├── Dashboard
    ├── Produkty
    ├── Warianty
    ├── Zdjęcia
    ├── Kolekcje
    ├── Gotowe kreacje
    ├── Zamówienia
    ├── Artykuły SEO
    ├── Statystyki
    └── AI Assistant
        ├── Generowanie opisów
        ├── Uzupełnianie danych produktu
        ├── Sugestie nowych produktów
        ├── Analiza sprzedaży
        └── Generowanie zdjęć / grafik
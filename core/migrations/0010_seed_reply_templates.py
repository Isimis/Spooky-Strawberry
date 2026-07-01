from django.db import migrations


# Gotowe szablony ręcznych odpowiedzi dla huba wiadomości (Obsługa klienta).
# Nie są systemowe (is_system=False) — obsługa może je swobodnie edytować.
# W kontekście ręcznej wysyłki dostępne są pola: {{ first_name }} oraz {{ email }}.
# Treść jest automatycznie owijana w szablon bazowy maili.

GREETING = "<p>Cześć{% if first_name %} {{ first_name }}{% endif %}! 🍓</p>"
SIGNOFF = "<p>Pozdrawiamy,<br>Zespół Spooky Strawberry 🖤</p>"


REPLY_TEMPLATES = [
    {
        "system_key": "reply-order-status",
        "name": "Zamówienie — status / gdzie moja paczka",
        "subject": "Status Twojego zamówienia — Spooky Strawberry 🍓",
        "description": "Odpowiedź, gdy klient pyta, na jakim etapie jest jego zamówienie.",
        "body_html": (
            GREETING
            + "<p>Już sprawdzamy Twoje zamówienie! Aktualny status to: <strong>[STATUS]</strong>.</p>"
            "<p>Numer przesyłki: <strong>[NUMER PRZESYŁKI]</strong> — możesz śledzić ją tutaj: "
            "<a href=\"[LINK DO ŚLEDZENIA]\">[LINK DO ŚLEDZENIA]</a>.</p>"
            "<p>Gdyby coś się nie zgadzało, daj znać — jesteśmy tu dla Ciebie.</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-shipping-delay",
        "name": "Wysyłka — przeprosiny za opóźnienie",
        "subject": "W sprawie Twojego zamówienia — mały poślizg 🦇",
        "description": "Gdy wysyłka się opóźnia i chcemy uprzedzić / przeprosić klienta.",
        "body_html": (
            GREETING
            + "<p>Piszemy, bo Twoje zamówienie <strong>[NUMER ZAMÓWIENIA]</strong> wyjdzie od nas "
            "z lekkim opóźnieniem. Bardzo Cię za to przepraszamy!</p>"
            "<p>Przewidywana data nadania to <strong>[DATA]</strong>. Damy znać osobnym mailem, "
            "gdy tylko paczka ruszy w drogę.</p>"
            "<p>Dziękujemy za cierpliwość i wyrozumiałość 🖤</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-restock",
        "name": "Produkt — powrót do sprzedaży (restock)",
        "subject": "Wracamy z tym produktem 🖤 — Spooky Strawberry",
        "description": "Odpowiedź na pytanie o dostępność / kiedy produkt wróci na stan.",
        "body_html": (
            GREETING
            + "<p>Dziękujemy za zainteresowanie <strong>[NAZWA PRODUKTU]</strong>! "
            "Ten model jest teraz wyprzedany, ale planujemy jego powrót około <strong>[DATA]</strong>.</p>"
            "<p>Jeśli chcesz, zapisz się do newslettera — informujemy o dropach i restockach "
            "zanim znikną. Możemy też przypomnieć Ci osobiście, gdy tylko wróci na stan.</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-return-howto",
        "name": "Zwrot — jak zwrócić zamówienie",
        "subject": "Jak zwrócić zamówienie — Spooky Strawberry",
        "description": "Instrukcja zwrotu wysyłana na prośbę klienta.",
        "body_html": (
            GREETING
            + "<p>Jasne, chętnie pomożemy ze zwrotem. Masz na to <strong>30 dni</strong> od otrzymania paczki. "
            "Wystarczy, że:</p>"
            "<ol>"
            "<li>Zapakujesz produkt(y) z metkami, w nienoszonym stanie.</li>"
            "<li>Dołączysz numer zamówienia: <strong>[NUMER ZAMÓWIENIA]</strong>.</li>"
            "<li>Odeślesz paczkę na adres: <strong>[ADRES ZWROTU]</strong>.</li>"
            "</ol>"
            "<p>Po otrzymaniu zwrotu oddamy pieniądze w ciągu kilku dni roboczych na tę samą metodę płatności. "
            "Gdyby coś było niejasne — pisz śmiało!</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-return-received",
        "name": "Zwrot — otrzymaliśmy przesyłkę",
        "subject": "Otrzymaliśmy Twój zwrot 🍓 — Spooky Strawberry",
        "description": "Potwierdzenie, że zwrot do nas dotarł i jest w realizacji.",
        "body_html": (
            GREETING
            + "<p>Twój zwrot do zamówienia <strong>[NUMER ZAMÓWIENIA]</strong> dotarł do nas — dziękujemy!</p>"
            "<p>Sprawdzamy zawartość i zwracamy środki (<strong>[KWOTA]</strong>) na Twoją metodę płatności "
            "w ciągu <strong>[LICZBA]</strong> dni roboczych. Damy znać, gdy przelew ruszy.</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-refund-done",
        "name": "Zwrot środków — zrealizowany",
        "subject": "Zwrot środków zrealizowany — Spooky Strawberry",
        "description": "Informacja, że pieniądze zostały zwrócone klientowi.",
        "body_html": (
            GREETING
            + "<p>Dobre wieści — zwróciliśmy <strong>[KWOTA]</strong> za zamówienie "
            "<strong>[NUMER ZAMÓWIENIA]</strong> na Twoją metodę płatności.</p>"
            "<p>W zależności od banku środki mogą pojawić się na koncie w ciągu 1–5 dni roboczych.</p>"
            "<p>Mamy nadzieję, że jeszcze się u nas zobaczymy 🖤</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-exchange",
        "name": "Wymiana — inny rozmiar / model",
        "subject": "Wymiana rozmiaru — Spooky Strawberry",
        "description": "Odpowiedź, gdy klient chce wymienić produkt na inny rozmiar lub model.",
        "body_html": (
            GREETING
            + "<p>Oczywiście, pomożemy z wymianą! Chcesz wymienić <strong>[PRODUKT / ROZMIAR]</strong> "
            "na <strong>[NOWY PRODUKT / ROZMIAR]</strong> — dobrze rozumiemy?</p>"
            "<p>Odeślij do nas produkt (z metkami, nienoszony) na adres <strong>[ADRES ZWROTU]</strong> "
            "z dopiskiem numeru zamówienia <strong>[NUMER ZAMÓWIENIA]</strong>. Gdy paczka dotrze, "
            "wyślemy nowy rozmiar — jeśli będzie dostępny, rezerwujemy go już teraz.</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-size-help",
        "name": "Pomoc — dobór rozmiaru",
        "subject": "Pomożemy dobrać rozmiar 🍓 — Spooky Strawberry",
        "description": "Wsparcie przy wyborze rozmiaru przed zakupem.",
        "body_html": (
            GREETING
            + "<p>Chętnie pomożemy dobrać idealny rozmiar!</p>"
            "<p>Napisz nam proszę swój wzrost, obwód w biuście, talii i biodrach — dopasujemy model "
            "<strong>[NAZWA PRODUKTU]</strong> do Twojej sylwetki.</p>"
            "<p>Pełną tabelę rozmiarów znajdziesz też przy każdym produkcie oraz tutaj: "
            "<a href=\"[LINK DO TABELI ROZMIARÓW]\">tabela rozmiarów</a>.</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-complaint-received",
        "name": "Reklamacja — przyjęcie zgłoszenia",
        "subject": "Przyjęliśmy Twoją reklamację — Spooky Strawberry",
        "description": "Potwierdzenie przyjęcia reklamacji wady produktu.",
        "body_html": (
            GREETING
            + "<p>Przykro nam, że produkt z zamówienia <strong>[NUMER ZAMÓWIENIA]</strong> nie spełnił "
            "Twoich oczekiwań. Traktujemy to poważnie.</p>"
            "<p>Twoje zgłoszenie zostało przyjęte i rozpatrzymy je w ciągu <strong>14 dni</strong>. "
            "Gdybyśmy potrzebowali dodatkowych zdjęć lub informacji, odezwiemy się do Ciebie.</p>"
            "<p>Dziękujemy, że dałaś nam znać 🖤</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-complaint-approved",
        "name": "Reklamacja — rozpatrzona pozytywnie",
        "subject": "Twoja reklamacja — rozpatrzona pozytywnie 🖤",
        "description": "Informacja o uznaniu reklamacji i dalszych krokach.",
        "body_html": (
            GREETING
            + "<p>Mamy dla Ciebie dobre wieści — Twoja reklamacja do zamówienia "
            "<strong>[NUMER ZAMÓWIENIA]</strong> została uznana.</p>"
            "<p>W ramach rozwiązania proponujemy: <strong>[WYMIANA / ZWROT ŚRODKÓW / NOWY PRODUKT]</strong>. "
            "[SZCZEGÓŁY DALSZYCH KROKÓW]</p>"
            "<p>Jeszcze raz przepraszamy za kłopot i dziękujemy za wyrozumiałość.</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-goodwill-code",
        "name": "Przeprosiny — kod rabatowy (gest dobrej woli)",
        "subject": "Coś od nas w ramach przeprosin 🍓",
        "description": "Kod rabatowy jako gest dobrej woli po problemie z zamówieniem.",
        "body_html": (
            GREETING
            + "<p>Jeszcze raz przepraszamy za zamieszanie z Twoim zamówieniem. Zależy nam, "
            "żeby zostało po tym dobre wrażenie.</p>"
            "<p>W ramach przeprosin przygotowaliśmy dla Ciebie kod: <strong>[KOD RABATOWY]</strong> "
            "— <strong>[WARTOŚĆ]</strong> na kolejne zakupy, ważny do <strong>[DATA]</strong>.</p>"
            "<p>Mamy nadzieję, że jeszcze się u nas zobaczymy 🦇</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-order-cancelled",
        "name": "Zamówienie — potwierdzenie anulowania",
        "subject": "Twoje zamówienie zostało anulowane — Spooky Strawberry",
        "description": "Potwierdzenie anulowania zamówienia na prośbę klienta.",
        "body_html": (
            GREETING
            + "<p>Zgodnie z Twoją prośbą anulowaliśmy zamówienie <strong>[NUMER ZAMÓWIENIA]</strong>.</p>"
            "<p>Jeśli płatność została już zaksięgowana, zwrócimy pełną kwotę "
            "(<strong>[KWOTA]</strong>) na tę samą metodę płatności w ciągu kilku dni roboczych.</p>"
            "<p>Będzie nam miło, gdy wrócisz do nas w lepszym momencie 🖤</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-wrong-address",
        "name": "Dostawa — problem z adresem",
        "subject": "Potrzebujemy potwierdzić adres dostawy — Spooky Strawberry",
        "description": "Gdy paczka wróciła lub adres wygląda na niepełny/błędny.",
        "body_html": (
            GREETING
            + "<p>Piszemy w sprawie dostawy zamówienia <strong>[NUMER ZAMÓWIENIA]</strong>. "
            "Wygląda na to, że z adresem coś się nie zgadza i paczka do nas wróciła / nie mogła zostać doręczona.</p>"
            "<p>Czy możesz potwierdzić prawidłowy adres dostawy (ulica, kod pocztowy, miasto)? "
            "Gdy tylko go otrzymamy, nadamy paczkę ponownie.</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-review-request",
        "name": "Prośba o opinię / recenzję",
        "subject": "Jak Ci się podoba? Podziel się opinią 🍓",
        "description": "Prośba o recenzję po dostarczeniu zamówienia.",
        "body_html": (
            GREETING
            + "<p>Mamy nadzieję, że kochasz swoje nowe rzeczy tak samo mocno jak my! 🖤</p>"
            "<p>Jeśli znajdziesz chwilę, będziemy wdzięczni za opinię o zamówieniu "
            "<strong>[NUMER ZAMÓWIENIA]</strong> — pomaga nam rosnąć i innym w wyborze.</p>"
            "<p><a href=\"[LINK DO OPINII]\">Zostaw opinię tutaj</a></p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-collab",
        "name": "Współpraca / influencer — odpowiedź",
        "subject": "W sprawie współpracy — Spooky Strawberry 🦇",
        "description": "Odpowiedź na zapytania o współpracę, barter, ambasadorstwo.",
        "body_html": (
            GREETING
            + "<p>Dziękujemy za wiadomość i zainteresowanie współpracą ze Spooky Strawberry!</p>"
            "<p>Chętnie dowiemy się więcej. Prześlij nam proszę link do swojego profilu, "
            "zasięgi oraz krótki pomysł na współpracę — a wrócimy z konkretami.</p>"
            "<p>Trzymamy kciuki za wspólne, mroczne projekty 🖤</p>"
            + SIGNOFF
        ),
    },
    {
        "system_key": "reply-general-thanks",
        "name": "Ogólna — dziękujemy za wiadomość",
        "subject": "Dziękujemy za wiadomość — Spooky Strawberry 🍓",
        "description": "Uniwersalna, neutralna odpowiedź na wiadomość z formularza kontaktowego.",
        "body_html": (
            GREETING
            + "<p>Dziękujemy za Twoją wiadomość — cieszymy się, że piszesz!</p>"
            "<p>[TREŚĆ ODPOWIEDZI]</p>"
            "<p>Gdybyś miała jeszcze jakiekolwiek pytania, śmiało odpisz na tego maila.</p>"
            + SIGNOFF
        ),
    },
]


def seed(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    for data in REPLY_TEMPLATES:
        MessageTemplate.objects.update_or_create(
            system_key=data["system_key"],
            defaults={
                "name": data["name"],
                "subject": data["subject"],
                "description": data["description"],
                "body_html": data["body_html"],
                "is_system": False,
                "is_active": True,
            },
        )


def unseed(apps, schema_editor):
    MessageTemplate = apps.get_model("core", "MessageTemplate")
    keys = [data["system_key"] for data in REPLY_TEMPLATES]
    MessageTemplate.objects.filter(system_key__in=keys).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_message_read_at"),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]

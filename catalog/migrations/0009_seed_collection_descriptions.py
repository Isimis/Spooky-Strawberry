from django.db import migrations


CATEGORY_DESCRIPTIONS = {
    "Chokery": "Chokery do alternatywnych stylizacji – od delikatnych akcentów po wyraziste dodatki, które podkreślają charakter looku.",
    "Mankiety": "Mankiety i dodatki na ręce do stylizacji soft goth, dark coquette, grunge i innych alternatywnych klimatów.",
    "Mitenki": "Mitenki i rękawiczki bez palców, które dodają stylizacji warstw, kontrastu i odrobiny mroku.",
    "Podkolanówki": "Podkolanówki do codziennych i bardziej odważnych stylizacji alternatywnych – do spódnic, platform i wysokich butów.",
    "Podwiązki": "Podwiązki jako detal do stylizacji dark coquette, goth i grunge. Mały dodatek, który zmienia cały look.",
    "Pończochy": "Pończochy do alternatywnych stylizacji – wybierz detal, który dopełni spódnicę, sukienkę albo dłuższy sweter.",
    "Rajstopy": "Rajstopy i kabaretki do stylizacji alternatywnych. Łącz je ze spódnicami, szortami i wysokimi butami po swojemu.",
    "Skarpetki": "Skarpetki jako widoczny detal stylizacji – do sneakersów, balerin, platform i wszystkiego pomiędzy.",
    "Spinki do włosów": "Spinki do włosów i drobne akcesoria, które dopełniają fryzurę oraz alternatywny look.",
}

AESTHETIC_DESCRIPTIONS = {
    "Soft Goth": "Soft goth łączy mroczne detale z delikatnością. Koronki, krzyże, czerń, róż i dodatki, które pozwalają budować klimat po swojemu.",
    "Witchy": "Witchy to codzienna magia, srebrne detale i mroczna elegancja. Odkryj dodatki, które pasują do intuicyjnego, trochę tajemniczego looku.",
    "Goth": "Goth stawia na czerń, kontrast i wyraziste detale. Zobacz dodatki do stylizacji, które nie potrzebują tłumaczenia.",
    "Jirai kei": "Jirai kei to kontrast słodyczy i mroku: kokardy, koronka, czerń, róż oraz detale, które robią teatralny klimat.",
    "Dark coquette": "Dark coquette łączy romantyczne kokardy i koronki z ciemniejszą stroną stylu. Buduj look warstwami i drobnymi akcesoriami.",
    "Grunge": "Grunge jest surowy, wygodny i bez udawania. Wybierz dodatki, które dobrze wyglądają w warstwowych, trochę niedbałych stylizacjach.",
    "Y2K": "Y2K to nostalgia lat 2000., mocne detale i odrobina chaosu. Odkryj dodatki, które ożywiają stylizację.",
    "Kawaii": "Kawaii to słodycz z charakterem. Drobne akcesoria pozwalają dodać do stylizacji kolor, kontrast i własny twist.",
    "Pastel Goth": "Pastel goth miesza pastele z ciemnymi detalami. To estetyka dla osób, które lubią równocześnie delikatność i mrok.",
    "E-girl": "E-girl opiera się na wyrazistych detalach, warstwach i inspiracjach internetową modą. Wybierz dodatki, które dopełnią look.",
}


def seed_descriptions(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Aesthetic = apps.get_model("catalog", "Aesthetic")

    for name, description in CATEGORY_DESCRIPTIONS.items():
        Category.objects.filter(name=name, description="").update(description=description)
    for name, description in AESTHETIC_DESCRIPTIONS.items():
        Aesthetic.objects.filter(name=name, description="").update(description=description)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0008_aesthetic_featured_image")]

    operations = [migrations.RunPython(seed_descriptions, migrations.RunPython.noop)]

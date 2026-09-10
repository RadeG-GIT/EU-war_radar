# Navod: jak spustit vlastni EU War Radar zdarma (bez programovani)

Tenhle balicek obsahuje vse potrebne. Ty jen projdes kroky nize - trva to
tak 15-20 minut, jen jednou.

## Co budes potrebovat
- E-mailovou adresu
- 15 minut casu
- Nic placeneho - vsechno v tomto navodu je zdarma

---

## Krok 1: Vytvor si GitHub ucet

1. Jdi na https://github.com/signup
2. Zadej e-mail, heslo, uzivatelske jmeno
3. Potvrd e-mail

GitHub je bezpecne, celosvetove pouzivane misto, kde muze appka "bydlet"
a kde ji GitHub kazdy den zdarma sam spusti.

## Krok 2: Vytvor novy repozitar (slozku pro projekt)

1. Po prihlaseni klikni vpravo nahore na **+** a pak **New repository**
2. Nazev: `eu-war-radar` (nebo jakykoliv jiny)
3. Nastav jako **Public**
4. Klikni **Create repository**

## Krok 3: Nahraj soubory z tohoto balicku

1. Na strance noveho repozitare klikni na **"uploading an existing file"**
   (nebo "Add file" -> "Upload files")
2. Přetáhni tam **VSECHNY** soubory a slozky z tohoto balicku a zachovej
   jejich strukturu:
   - `fetch_risk.py`
   - slozka `docs` (s `index.html` a `data.json` uvnitr)
   - slozka `.github` (s `workflows/update.yml` uvnitr)
   - tento navod
3. Dole klikni **Commit changes**

   Poznamka: GitHub ve webovem rozhrani nekdy nedovoli nahrat cele slozky
   najednou v starsich prohlizecich. Pokud se to nepovede, zkus nahrat
   soubory jednotlive a rucne v GitHubu vytvorit slozky `docs` a
   `.github/workflows` (kliknutim na "Add file" -> "Create new file" a
   napsanim naprikad `docs/index.html` jako nazvu - GitHub slozku vytvori
   sam).

## Krok 4: Zapni GitHub Pages (aby appka mela vlastni webovou adresu)

1. V repozitari jdi na **Settings** (nahore)
2. Vlevo klikni na **Pages**
3. U "Source" vyber **Deploy from a branch**
4. U "Branch" vyber **main** a slozku **/docs**
5. Klikni **Save**

Za par minut se ti tam objevi odkaz typu:
`https://tvoje-jmeno.github.io/eu-war-radar/`

To je tvoje appka. Otevri si ji v telefonu a pridej na plochu jako
zalozku - bude se chovat skoro jako normalni appka.

## Krok 5: Over, ze automaticka aktualizace funguje

1. V repozitari klikni na zalozku **Actions**
2. Pokud se GitHub zepta, jestli chces workflows povolit, klikni **I understand my workflows, go ahead and enable them**
3. Klikni na "Daily radar update" a pak vpravo na **Run workflow** ->
   **Run workflow** - spustis prvni aktualizaci rucne, at hned vidis,
   ze to funguje
4. Po par desitkach vterin obnov stranku - mel by se objevit zeleny
   fajfka. Tvoje appka na `docs/data.json` je aktualni.

Od teď se to bude opakovat **samo kazdy den v 6:00 UTC** (cca 7-8 rano
u nas), i kdyz vypnes pocitac a nikam se neprihlasis.

---

## Co dela skript uvnitr

`fetch_risk.py` kazdy den:
1. Stahne aktualni titulky z verejnych RSS kanalu (Reuters, Al Jazeera,
   NATO, AP, ISW)
2. Pro kazdou sledovanou oblast (Ukrajina, Pobalti, Kosovo-Srbsko,
   Podnestri) spocita jednoduche skore podle klicovych slov
3. Vysledek ulozi do `docs/data.json`
4. Appka (`docs/index.html`) si tato data pri kazdem otevreni nacte

## Dulezite upozorneni

Skore je automaticky odhad na zaklade poctu a typu zprav, ne odborna
zpravodajska ci vojenska analyza. Berit ho jako rychly orientacni
prehled, ne jako predikci ci zaklad pro dulezita rozhodnuti.

## Co dal, kdyz budes chtit appku vylepsit

Nemusis umet programovat - staci mi (Claude) rict, co chces zmenit, a
ja ti pripravim upraveny soubor, ktery zase jen nahradis v GitHubu.
Napady na dalsi kroky:
- pridat dalsi oblasti (Kavkaz, Blizky vychod, kyberneticke utoky)
- poslat upozorneni na e-mail/Telegram, kdyz skore prekroci hranici
- ukladat historii v case a zobrazit graf trendu
- presnejsi vypocet skore (napr. pres placene API se strukturovanymi
  daty misto RSS klicovych slov)

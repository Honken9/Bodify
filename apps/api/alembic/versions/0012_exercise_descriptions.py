"""Övningsbeskrivningar: kort utförandetext för alla inbyggda övningar

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-18

"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Kort "så gör du"-text per inbyggd övning. Skrivs bara till övningar
# som saknar egen beskrivning (användarnas egna texter rörs aldrig).
DESCRIPTIONS = {
    "Bänkpress": "Ligg på bänken med fötterna i golvet och skulderbladen ihopdragna. Sänk stången kontrollerat till bröstet och pressa upp tills armarna är raka.",
    "Lutande bänkpress": "Som bänkpress men på lutande bänk (30–45°) — flyttar fokus till övre bröstet. Sänk stången mot nyckelbenen och pressa upp.",
    "Hantelpress": "Ligg på bänk med en hantel i varje hand vid bröstet. Pressa upp tills armarna är raka och sänk långsamt tillbaka — större rörelsebana än stång.",
    "Lutande hantelpress": "Hantelpress på lutande bänk. Pressa hantlarna upp och lätt inåt, sänk kontrollerat till bröstnivå.",
    "Flyes med hantlar": "Ligg på bänk med lätt böjda armar rakt upp. Sänk hantlarna ut åt sidorna i en vid båge tills du känner sträckning i bröstet, och för ihop igen.",
    "Kabelflyes": "Stå mellan kabelstationerna med handtagen i axelhöjd. För armarna framåt-ihop i en båge med lätt böjda armbågar. Konstant spänning hela vägen.",
    "Armhävningar": "Höft och rygg i rak linje, händerna strax bredare än axlarna. Sänk bröstet mot golvet och pressa upp. Går att försvåra med fötterna upphöjda.",
    "Dips": "Häng i räcket med raka armar, luta överkroppen lätt framåt. Sänk dig tills axlarna är i armbågshöjd och pressa upp. Framåtlutning = mer bröst.",
    "Bröstpress i maskin": "Ställ in sitsen så handtagen är i bröstnivå. Pressa framåt utan att låsa armbågarna helt och släpp tillbaka långsamt.",
    "Pec deck": "Sitt med ryggen mot dynan, underarmar/handtag i axelhöjd. Pressa ihop framför bröstet och släpp kontrollerat tillbaka.",
    "Marklyft": "Stå med stången över mittfoten. Böj i höft och knä, greppa stången, spänn bålen och lyft genom att pressa ifrån med benen — rak rygg hela vägen upp till stående.",
    "Rumänska marklyft": "Utgå stående med stången i händerna. Skjut höften bakåt och sänk stången längs benen med nästan raka knän tills baksidan stramar, och res dig med höften.",
    "Skivstångsrodd": "Fäll överkroppen ~45° med rak rygg, stången hängande. Dra stången mot naveln med armbågarna nära kroppen och sänk kontrollerat.",
    "Hantelrodd": "Stöd ena knät och handen på en bänk. Dra hanteln mot höften med armbågen nära kroppen, sänk långsamt. Byt sida.",
    "Sittande kabelrodd": "Sitt med lätt böjda knän och rak rygg. Dra handtaget mot magen, kläm ihop skulderbladen, och släpp fram kontrollerat.",
    "Latsdrag": "Sitt med låren låsta under kudden. Dra stången till övre bröstet med bred fattning och släpp upp långsamt — undvik att luta dig bakåt för mycket.",
    "Pull-ups": "Häng med pronerat grepp (handflatorna ifrån dig), något bredare än axlarna. Dra dig upp tills hakan passerar stången och sänk helt kontrollerat.",
    "Chins": "Som pull-ups men med supinerat grepp (handflatorna mot dig), axelbrett — mer biceps. Dra upp, sänk långsamt, full rörelsebana.",
    "T-bar rodd": "Grensla stången med bröstet lätt framåtlutat och rak rygg. Dra handtaget mot bröstet och sänk kontrollerat.",
    "Face pulls": "Sätt kabeln i ansiktshöjd med rep. Dra repet mot ansiktet med höga armbågar och rotera ut händerna — toppen för hållning och bakre axlar.",
    "Hyperextensions": "I romerska stolen: fäll överkroppen ner med rak rygg och lyft tillbaka till rak linje. Kläm sätet i toppen, undvik översträckning.",
    "Shrugs": "Stå med hantlar eller stång hängande. Dra axlarna rakt upp mot öronen, håll en sekund och sänk. Inga rullande rörelser.",
    "Knäböj": "Stången på övre ryggen, fötter axelbrett. Böj knä och höft som att sätta dig på en stol, ner till minst parallellt, och pressa upp genom hela foten.",
    "Frontböj": "Stången vilar fram på axlarna med höga armbågar. Böj djupt med upprätt överkropp — mer framsida lår och bål än vanlig knäböj.",
    "Benpress": "Fötter axelbrett mitt på plattan. Sänk vikten tills knäna når ~90° och pressa ut utan att låsa knäna helt.",
    "Utfall": "Ta ett stort kliv framåt och sänk bakre knät mot golvet. Pressa tillbaka till stående via främre hälen. Överkroppen upprätt.",
    "Gående utfall": "Som utfall men du fortsätter framåt steg för steg. Jämna, kontrollerade kliv med upprätt överkropp.",
    "Bulgarska utfall": "Bakre foten på en bänk, främre benet arbetar. Sänk rakt ner tills främre låret är parallellt och pressa upp. Tufft för balans och säte.",
    "Benspark": "Sitt i maskinen med vristerna bakom rullen. Sträck ut benen kontrollerat och sänk långsamt — stanna strax innan vikterna slår i.",
    "Liggande lårcurl": "Ligg på mage i maskinen, rullen mot hälsenorna. Böj knäna och dra rullen mot sätet, sänk långsamt tillbaka.",
    "Sittande lårcurl": "Sitt i maskinen med benen över rullen. Böj knäna och pressa rullen ner-bakåt, återgå kontrollerat.",
    "Stående vadpress": "Stå på trampkanten med hälarna fritt. Sjunk ner i en djup sträckning och pressa upp på tå så högt du kan. Pausa i toppen.",
    "Sittande vadpress": "Som stående men sittande med vikten på knäna — träffar djupare vadmuskeln (soleus). Full rörelse, långsam negativ.",
    "Höftlyft": "Övre ryggen mot en bänk, skivstång eller vikt över höften. Pressa upp höften tills kroppen är rak och kläm sätet hårt i toppen.",
    "Goblet squat": "Håll en hantel eller kettlebell mot bröstet med båda händerna. Böj djupt med upprätt överkropp — utmärkt teknikbyggare.",
    "Step-ups": "Kliv upp på en bänk eller låda med hela foten, pressa upp via hälen och kliv ner kontrollerat. Byt ben.",
    "Militärpress": "Stå med stången vid nyckelbenen, axelbrett grepp. Pressa rakt upp över huvudet utan bensving och sänk kontrollerat. Spänn bål och säte.",
    "Axelpress med hantlar": "Sitt eller stå med hantlarna i axelhöjd. Pressa upp tills armarna är raka och sänk långsamt — hantlarna tillåter en naturligare bana än stång.",
    "Arnoldpress": "Starta med hantlarna framför axlarna, handflator mot dig. Rotera ut händerna under pressen så handflatorna pekar framåt i toppen.",
    "Sidolyft": "Stå med hantlar längs sidorna. Lyft armarna rakt ut åt sidorna till axelhöjd med lätt böjda armbågar och sänk långsamt. Lätta vikter, ren teknik.",
    "Framlyft": "Lyft hanteln/skivan rakt fram till axelhöjd med raka armar och sänk kontrollerat. Undvik gung.",
    "Omvända flyes": "Fäll överkroppen framåt med hantlar hängande. Lyft armarna ut åt sidorna som vingar — träffar bakre axlar och övre rygg.",
    "Sidolyft i kabel": "Som sidolyft men i kabel — konstant spänning genom hela rörelsen. Stå sidledes mot maskinen och lyft ut från kroppen.",
    "Push press": "Som militärpress men med ett litet knäsvikt som hjälper vikten förbi startläget. Explosivt upp, kontrollerat ner.",
    "Bicepscurl med skivstång": "Stå med axelbrett underhandsgrepp. Curla stången mot axlarna utan att gunga och sänk långsamt. Armbågarna stilla vid sidorna.",
    "Hantelcurl": "Curla hantlarna växelvis eller samtidigt med handflatorna uppåt. Full sträckning i botten, ingen sving.",
    "Hammercurl": "Som hantelcurl men med neutralt grepp (tummarna uppåt) — träffar även underarmarna. Kontrollerad rörelse hela vägen.",
    "Predikatorcurl": "Överarmarna vilar på predikatorbänken. Curla upp och sänk djupt kontrollerat — omöjligt att fuska.",
    "Kabelcurl": "Curl i kabel med konstant spänning. Armbågarna stilla, kläm i toppen, långsam negativ.",
    "Pushdowns": "Stå vid kabeln med armbågarna låsta vid sidorna. Pressa handtaget rakt ner tills armarna är raka och släpp upp kontrollerat.",
    "Fransk press": "Ligg på bänk med stången rakt upp. Böj enbart armbågarna och sänk stången mot pannan, pressa tillbaka upp.",
    "Tricepsextension över huvudet": "Håll hantel eller rep bakom huvudet med armbågarna uppåt. Sträck armarna rakt upp och sänk långsamt bakom nacken.",
    "Smal bänkpress": "Bänkpress med axelbrett grepp och armbågarna nära kroppen — flyttar jobbet till triceps. Sänk till nedre bröstet.",
    "Bänkdips": "Händerna på en bänk bakom dig, benen framför. Sänk höften mot golvet genom att böja armarna och pressa upp. Svårare med fötter på upphöjning.",
    "Plankan": "Stå på underarmar och tår med kroppen i en rak linje. Spänn mage och säte — sjunk inte ner i ländryggen. Håll tiden.",
    "Sidoplanka": "Ligg på sidan med stöd på underarmen, lyft höften så kroppen bildar en rak linje. Håll — byt sida.",
    "Sit-ups": "Ligg med böjda knän. Rulla upp överkroppen mot knäna med kontrollerad rörelse och sänk långsamt tillbaka.",
    "Hängande benlyft": "Häng i räcket och lyft benen (böjda eller raka) mot bröstet utan gung. Sänk långsamt — bäst i långsamt tempo.",
    "Cable crunch": "Knästående vid kabeln med repet bakom huvudet. Rulla ihop överkroppen mot golvet med magen, inte armarna.",
    "Russian twists": "Sitt tillbakalutad med fötterna lätt lyfta. Rotera överkroppen sida till sida, gärna med vikt. Kontrollerat tempo.",
    "Ab wheel": "Rulla hjulet framåt från knästående så långt du kan hålla höft och rygg rak, och dra tillbaka med magen. Brutalt effektiv.",
    "Pallof press": "Stå sidledes mot kabeln med handtaget vid bröstet. Pressa armarna rakt fram och stå emot rotationen. Anti-rotationsträning för bålen.",
    "Kettlebell swings": "Svinga kettlebellen mellan benen och driv den till bröst-/ögonhöjd med en explosiv höftsträckning — armarna är bara remmar. Kraften kommer från höften.",
    "Thrusters": "Frontböj som exploderar upp i en press över huvudet i en enda flytande rörelse. Hela kroppen, hög puls.",
    "Burpees": "Ner i armhävning, upp till stående, avsluta med ett hopp. Hela kroppen och konditionen — hitta en jämn rytm.",
    "Farmer's walk": "Gå med tunga hantlar eller kettlebells i händerna, upprätt hållning och spänd bål. Greppet, bålen och traps jobbar.",
    "Clean & press": "Lyft vikten explosivt från golvet till axlarna (clean) och pressa den sedan över huvudet. Teknikkrävande helkroppsövning.",
}


def upgrade() -> None:
    op.add_column("exercises", sa.Column("description", sa.Text(), nullable=True))
    for name, text in DESCRIPTIONS.items():
        op.execute(
            sa.text(
                "UPDATE exercises SET description = :text "
                "WHERE name = :name AND is_global = :glob AND description IS NULL"
            ).bindparams(text=text, name=name, glob=True)
        )


def downgrade() -> None:
    op.drop_column("exercises", "description")

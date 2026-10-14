"""Austrian food words → the German names the BLS uses ("Faschiertes" → "Hackfleisch")."""
import re

AT_TO_DE = {
    "faschiertes": "hackfleisch", "faschiert": "hackfleisch", "paradeiser": "tomaten",
    "paradeis": "tomate", "erdäpfel": "kartoffeln", "erdapfel": "kartoffel", "topfen": "quark",
    "obers": "sahne", "schlagobers": "sahne", "sauerrahm": "saure sahne", "karfiol": "blumenkohl",
    "marillen": "aprikosen", "marille": "aprikose", "kren": "meerrettich",
    "fisolen": "bohnen grün", "melanzani": "aubergine", "kohlsprossen": "rosenkohl",
    "semmel": "brötchen", "germ": "hefe", "eierschwammerl": "pfifferlinge",
    "ribisel": "johannisbeeren", "zwetschken": "pflaumen", "zwetschke": "pflaume",
    "vogerlsalat": "feldsalat", "kukuruz": "mais", "rote rüben": "rote bete", "rahm": "sahne",
    "hendl": "hähnchen", "huhn": "hähnchen", "pute": "truthahn", "powidl": "pflaumenmus",
    "dirndl": "kornelkirsche", "brösel": "paniermehl",
}


def to_german(query: str) -> str:
    """The query in lower case with Austrian words replaced (longest first)."""
    text = query.lower()
    for austrian, german in sorted(AT_TO_DE.items(), key=lambda kv: -len(kv[0])):
        text = re.sub(rf"\b{re.escape(austrian)}\b", german, text)
    return text

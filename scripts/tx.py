#!/usr/bin/env python3
"""
Shared translation lookup, using the same tx.json the weekly page build writes.

The site's tr() falls back to the source string when a translation is missing,
which is exactly why an untranslated week looks perfect in ES and half-Spanish
in EN with nothing in the build output to say so. The daily post inherits that
trap, so this module does the same lookup but *reports* every miss, and the
runner treats misses on an English account as a warning worth seeing.

Keys are the source string byte-for-byte -- never tidy its spacing, accents or
typos, because the untidy string is the key.
"""
import json, pathlib

TRANSLATABLE = ("title", "venue", "address", "price", "desc", "note")


class Tx:
    def __init__(self, path=None, lang="en"):
        self.lang, self.map, self.missing = lang, {}, []
        if path:
            p = pathlib.Path(path)
            if p.exists():
                self.map = json.loads(p.read_text(encoding="utf-8"))

    def t(self, s):
        s = (s or "")
        if not s.strip():
            return s
        hit = self.map.get(s)
        if isinstance(hit, dict) and hit.get(self.lang):
            return hit[self.lang]
        if isinstance(hit, str):
            return hit
        if _looks_translatable(s):
            self.missing.append(s)
        return s

    def row(self, e):
        out = dict(e)
        for f in TRANSLATABLE:
            if e.get(f):
                out[f] = self.t(e[f])
        return out

    def report(self):
        if not self.map:
            return "no tx.json loaded - strings pass through untranslated"
        if not self.missing:
            return "translation coverage complete"
        uniq = sorted(set(self.missing))
        return ("%d string(s) with no %s translation: %s"
                % (len(uniq), self.lang.upper(),
                   " | ".join(u[:44] for u in uniq[:6])
                   + (" ..." if len(uniq) > 6 else "")))


# Spanish function words are the cheap, reliable tell. A proper noun ("Teatro
# ABA", "Kafu Banton") has none of them and correctly stays as written, so it
# is not reported as a miss.
# Accents alone are NOT a tell: "Danilo Pérez Trio" and "Teatro Amador" are
# proper nouns that correctly stay as written. Only function words and
# Spanish-specific vocabulary count, or the report drowns in false positives
# and stops being read -- which is the same failure as not having it.
_ES_HINT = (" de ", " del ", " la ", " el ", " los ", " las ", " con ",
            " en ", " y ", " para ", " por ", "ción", "preventa", "puerta",
            "gratis", "entrada", "entradas", "desde", "niños", "menores",
            "tercera edad", "cargos", "taller", "noche de", "boletos")


def _looks_translatable(s):
    low = " %s " % s.lower()
    return any(h in low for h in _ES_HINT)

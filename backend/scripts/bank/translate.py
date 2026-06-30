"""Translate + quality-filter an English QuestionDraft into French via Claude.

One Claude call per question (raw httpx on the Anthropic Messages API — no SDK),
with a persistent JSON cache keyed by the SHA-1 of the English question so a
string is never translated twice. Claude also judges cultural relevance for a
French audience: garder=false drops US-centric / untranslatable / poor questions.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from scripts.bank.opentriviaqa import QuestionDraft

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"

_SYSTEM = (
    "Tu adaptes des questions de quiz anglaises pour une soirée quiz francophone. "
    "Traduis fidèlement en français la question, les quatre choix et la bonne réponse. "
    "Mets \"garder\": false dans l'un de ces cas : "
    "(1) question trop spécifiquement américaine/anglo-saxonne ou sans intérêt pour un public français ; "
    "(2) intraduisible (jeu de mots, référence culturelle qui ne passe pas) ; "
    "(3) réponse factuellement fausse, contestable, datée, ou dont la bonne réponse prête à débat ; "
    "(4) formulation ambiguë ou piège de définition (ex. « entièrement dans l'hémisphère… ») "
    "où plusieurs réponses pourraient se défendre. "
    "Dans le doute sur la justesse de la réponse, mets \"garder\": false plutôt que de l'inclure. "
    "\"bonne_reponse\" doit être exactement l'un des quatre choix traduits. "
    "Estime la difficulté : facile, moyen ou difficile."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "garder": {"type": "boolean"},
        "question": {"type": "string"},
        "choix": {"type": "array", "items": {"type": "string"}},
        "bonne_reponse": {"type": "string"},
        "difficulte": {"type": "string", "enum": ["facile", "moyen", "difficile"]},
    },
    "required": ["garder", "question", "choix", "bonne_reponse", "difficulte"],
    "additionalProperties": False,
}


@dataclass
class TranslatedQuestion:
    question: str
    answer: str
    choices: list[str]
    difficulty: str


def _cache_path() -> Path:
    return Path(os.environ.get("TRANSLATION_CACHE", "data/translation_cache.json"))


def _load_cache() -> dict:
    p = _cache_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict) -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _call_claude(draft: QuestionDraft) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY manquante : exporte-la avant de traduire.")
    model = os.environ.get("TRANSLATE_MODEL", DEFAULT_MODEL)
    user = (
        f"Question : {draft.question}\n"
        f"Choix : {' | '.join(draft.choices)}\n"
        f"Bonne réponse : {draft.answer}"
    )
    body = {
        "model": model,
        "max_tokens": 1024,
        "system": _SYSTEM,
        "messages": [{"role": "user", "content": user}],
        "output_config": {"format": {"type": "json_schema", "schema": _SCHEMA}},
    }
    resp = httpx.post(
        API_URL,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=body,
        timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    text = next((b["text"] for b in data["content"] if b["type"] == "text"), None)
    if text is None:
        raise RuntimeError(f"Réponse Claude sans bloc texte : stop_reason={data.get('stop_reason')!r}")
    return json.loads(text)


def translate_question(draft: QuestionDraft) -> TranslatedQuestion | None:
    cache = _load_cache()
    key = hashlib.sha1(draft.question.encode("utf-8")).hexdigest()
    if key in cache:
        result = cache[key]
    else:
        result = _call_claude(draft)
        # On met TOUT en cache, y compris les rejets (garder=false), pour ne jamais
        # re-juger ni re-payer la même question. Pour ré-évaluer des rejets après avoir
        # changé le prompt, supprimer le fichier de cache (TRANSLATION_CACHE).
        cache[key] = result
        _save_cache(cache)
    if not result.get("garder"):
        return None
    choix = [str(c).strip() for c in (result.get("choix") or [])]
    bonne = str(result.get("bonne_reponse") or "").strip()
    if len(choix) != 4 or bonne not in choix:
        return None
    # Défensif : le json_schema (enum) contraint déjà la difficulté côté API ; ce repli
    # ne se déclenche que si la contrainte n'est pas respectée.
    diff = result.get("difficulte")
    if diff not in ("facile", "moyen", "difficile"):
        diff = "inconnu"
    return TranslatedQuestion(
        question=str(result.get("question") or "").strip(),
        answer=bonne, choices=choix, difficulty=diff,
    )

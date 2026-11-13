"""Collegamento con WhatsApp Cloud API (Meta)."""
import hashlib
import hmac
import logging
import os

import httpx

log = logging.getLogger("whatsapp")


def firma_valida(app_secret, corpo, intestazione):
    """Controlla l'intestazione X-Hub-Signature-256 che Meta mette su ogni webhook."""
    if not app_secret or not intestazione or not intestazione.startswith("sha256="):
        return False
    atteso = hmac.new(app_secret.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(atteso, intestazione.removeprefix("sha256="))


def messaggi_in_arrivo(payload):
    """Estrae i messaggi dei clienti da un webhook: [{phone_number_id, da, nome, id, tipo, testo}]."""
    out = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            v = change.get("value", {}) or {}
            numero = (v.get("metadata") or {}).get("phone_number_id")
            nomi = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in v.get("contacts", []) or []}
            for m in v.get("messages", []) or []:
                tipo = m.get("type", "")
                testo = ""
                if tipo == "text":
                    testo = (m.get("text") or {}).get("body", "")
                elif tipo == "button":
                    testo = (m.get("button") or {}).get("text", "")
                elif tipo == "interactive":
                    i = m.get("interactive") or {}
                    testo = (i.get("button_reply") or i.get("list_reply") or {}).get("title", "")
                out.append({"phone_number_id": numero, "da": m.get("from", ""), "nome": nomi.get(m.get("from"), ""),
                            "id": m.get("id", ""), "tipo": tipo, "testo": testo.strip()})
    return out


class Mittente:
    """Invia messaggi. In prova si sostituisce con un finto mittente."""

    def __init__(self, token=None, versione=None):
        self.token = token or os.environ.get("WA_TOKEN", "")
        self.versione = versione or os.environ.get("GRAPH_VERSION", "v23.0")

    def _invia(self, phone_number_id, corpo):
        url = f"https://graph.facebook.com/{self.versione}/{phone_number_id}/messages"
        r = httpx.post(url, json={"messaging_product": "whatsapp", **corpo},
                       headers={"Authorization": f"Bearer {self.token}"}, timeout=20)
        if r.status_code >= 400:
            log.error("WhatsApp ha rifiutato il messaggio (%s): %s", r.status_code, r.text[:500])
            r.raise_for_status()
        return r.json()

    def testo(self, phone_number_id, a, testo):
        return self._invia(phone_number_id, {"to": a, "type": "text", "text": {"body": testo[:4000]}})

    def modello(self, phone_number_id, a, nome_modello, parametri, lingua="it"):
        """Messaggio da modello approvato da Meta: serve fuori dalla finestra di 24 ore (promemoria)."""
        return self._invia(phone_number_id, {
            "to": a, "type": "template",
            "template": {"name": nome_modello, "language": {"code": lingua},
                         "components": [{"type": "body",
                                         "parameters": [{"type": "text", "text": str(p)} for p in parametri]}]}})

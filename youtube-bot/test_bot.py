"""Test automatici dei bot (senza chiamare davvero YouTube o Claude).

Esegui:  python -m pytest -q test_bot.py
"""
import json
import sys
import types
from pathlib import Path

import pytest

import comune as c
import scrittore as s


# ------------------------------------------------------------ utilità
@pytest.fixture
def cartella(tmp_path, monkeypatch):
    """Sposta tutti i file dati in una cartella temporanea."""
    for nome, file in (("CONTENUTI", "contenuti.json"), ("PUBBLICATI", "pubblicati.json"),
                       ("STATISTICHE", "statistiche.json")):
        monkeypatch.setattr(c, nome, tmp_path / file)
    base = json.loads((Path(__file__).parent / "contenuti.json").read_text(encoding="utf-8"))
    c.scrivi(tmp_path / "contenuti.json", base)
    return tmp_path


def video_ok(**cambi):
    dati = dict(id="vulcani", titolo="5 segreti dei VULCANI", intro="Cinque segreti dei vulcani.",
                colori=["#5A1A0E", "#C0392B"], tag=["natura", "vulcani", "terra", "scienza", "lava"],
                fatti=["L'Etna è uno dei vulcani più attivi del mondo e si trova in Sicilia."] * 5)
    dati.update(cambi)
    return s.Video(**dati)


# ------------------------------------------------------------ controlli formali
def test_video_valido_passa():
    assert s.problemi_formali(video_ok(), set(), set()) == []


@pytest.mark.parametrize("cambio,atteso", [
    ({"id": "Vulcani!"}, "id non valido"),
    ({"colori": ["#FFFFFF", "#000000"]}, "colori troppo chiari per il testo bianco"),
    ({"colori": ["rosso", "#000000"]}, "colori non validi"),
    ({"fatti": ["Frase corta."] * 5}, "fatto 1 troppo corto o troppo lungo"),
    ({"fatti": ["Un fatto abbastanza lungo da essere valido per il test."] * 4}, "servono esattamente 5 fatti"),
    ({"titolo": "x" * 80}, "titolo vuoto o troppo lungo"),
    ({"tag": ["uno"]}, "tag non validi"),
])
def test_video_non_valido(cambio, atteso):
    assert atteso in s.problemi_formali(video_ok(**cambio), set(), set())


def test_doppioni_rifiutati():
    prob = s.problemi_formali(video_ok(), {"vulcani"}, {"5 segreti dei vulcani"})
    assert "id già usato" in prob and "titolo già usato" in prob


def test_colori_reali_dei_video_esistenti_sono_validi():
    base = json.loads((Path(__file__).parent / "contenuti.json").read_text(encoding="utf-8"))
    for v in base["video"]:
        assert s.problemi_formali(s.Video(**v), set(), set()) == [], v["id"]


# ------------------------------------------------------------ Scrittore + Verificatore
class RispostaFinta:
    def __init__(self, parsed, stop="end_turn"):
        self.parsed_output, self.stop_reason = parsed, stop


class ClientFinto:
    def __init__(self, lotto, verifica):
        self.risposte = [lotto, verifica]
        self.chiamate = []
        self.beta = types.SimpleNamespace(messages=types.SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.chiamate.append(kw)
        return self.risposte.pop(0)


def prepara_scrittore(monkeypatch, client):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "finta")
    modulo = types.SimpleNamespace(Anthropic=lambda: client)
    monkeypatch.setitem(sys.modules, "anthropic", modulo)
    monkeypatch.setattr(sys, "argv", ["scrittore.py", "--quanti", "3"])


def test_scrittore_aggiunge_solo_video_verificati(cartella, monkeypatch):
    lotto = s.Lotto(video=[video_ok(id="vulcani", titolo="5 segreti dei VULCANI"),
                           video_ok(id="api", titolo="5 curiosità sulle API"),
                           video_ok(id="squali", titolo="Doppione")])          # id già esistente
    controllo = s.Verifica(video=[
        s.ControlloVideo(id="vulcani", fatti=[s.ControlloFatto(numero=i, corretto=True, nota="") for i in range(1, 6)]),
        s.ControlloVideo(id="api", fatti=[s.ControlloFatto(numero=i, corretto=i != 3, nota="dubbio")
                                          for i in range(1, 6)]),
    ])
    client = ClientFinto(RispostaFinta(lotto), RispostaFinta(controllo))
    prepara_scrittore(monkeypatch, client)
    prima = len(c.leggi(c.CONTENUTI, {})["video"])
    s.main()
    dopo = c.leggi(c.CONTENUTI, {})["video"]
    assert [v["id"] for v in dopo[prima:]] == ["vulcani"]
    assert client.chiamate[0]["model"] == "claude-opus-5-5"
    assert client.chiamate[0]["fallbacks"] == "default"
    # il Verificatore riceve solo i candidati che hanno superato i controlli formali
    assert "squali" not in client.chiamate[1]["messages"][0]["content"].split("VIDEO id=")[-1]


def test_scrittore_gestisce_rifiuto(cartella, monkeypatch):
    client = ClientFinto(RispostaFinta(None, stop="refusal"), None)
    prepara_scrittore(monkeypatch, client)
    prima = len(c.leggi(c.CONTENUTI, {})["video"])
    s.main()
    assert len(c.leggi(c.CONTENUTI, {})["video"]) == prima


def test_scrittore_senza_chiave_si_ferma(cartella, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["scrittore.py", "--quanti", "2"])
    with pytest.raises(SystemExit):
        s.main()


def test_scrittore_non_scrive_se_coda_piena(cartella, monkeypatch, capsys):
    base = c.leggi(c.CONTENUTI, {})
    base["video"] = base["video"] * 2   # 20 in coda
    for i, v in enumerate(base["video"]):
        base["video"][i] = dict(v, id=f"{v['id']}-{i}")
    c.scrivi(c.CONTENUTI, base)
    monkeypatch.setattr(sys, "argv", ["scrittore.py"])
    s.main()
    assert "Da scrivere: 0" in capsys.readouterr().out


def test_preferenze_ordina_per_media():
    pubblicati = {"a": {"categoria": "spazio"}, "b": {"categoria": "cibo"}, "c": {"categoria": "spazio"}}
    stat = {"video": {"a": {"visualizzazioni": 100}, "b": {"visualizzazioni": 500}, "c": {"visualizzazioni": 300}}}
    assert [k for k, _ in s.preferenze(stat, pubblicati)] == ["cibo", "spazio"]


# ------------------------------------------------------------ Pubblicatore
class YouTubeFinto:
    def __init__(self, privacy="public"):
        self.privacy, self.corpi = privacy, []

    def videos(self):
        return self

    def insert(self, part, body, media_body):
        self.corpi.append(body)
        privacy = self.privacy
        return types.SimpleNamespace(next_chunk=lambda: (None, {"id": "abc123", "status": {"privacyStatus": privacy}}))


def test_pubblicatore_flusso_completo(cartella, monkeypatch, capsys):
    import genera_video as gv
    import pubblica_oggi as p
    yt = YouTubeFinto(privacy="private")
    monkeypatch.setattr(c, "youtube", lambda: yt)
    monkeypatch.setattr(gv, "USCITA", cartella / "uscita")
    monkeypatch.setattr(gv, "crea_video", lambda v, cfg, dest: Path(dest).write_bytes(b"mp4"))
    p.main()
    pub = c.leggi(c.PUBBLICATI, {})
    assert pub["squali"]["youtube_id"] == "abc123" and pub["squali"]["categoria"] == "animali"
    assert yt.corpi[0]["snippet"]["title"].endswith("#shorts")
    assert len(yt.corpi[0]["snippet"]["title"]) <= 100
    assert "::warning::" in capsys.readouterr().out   # video rimasto privato -> avviso
    p.main()   # il giorno dopo pubblica il video successivo
    assert list(c.leggi(c.PUBBLICATI, {})) == ["squali", "spazio"]


def test_pubblicatore_coda_vuota(cartella, monkeypatch):
    import pubblica_oggi as p
    c.scrivi(c.PUBBLICATI, {v["id"]: {} for v in c.leggi(c.CONTENUTI, {})["video"]})
    with pytest.raises(SystemExit):
        p.main()


def test_credenziali_mancanti(monkeypatch):
    for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(SystemExit, match="YT_CLIENT_ID"):
        c.youtube()


# ------------------------------------------------------------ Analista + Segretario
class Esegui:
    def __init__(self, dati):
        self.dati = dati

    def execute(self):
        return self.dati


class YouTubeStatFinto:
    def videos(self):
        return types.SimpleNamespace(list=lambda part, id: Esegui({"items": [
            {"id": yid, "statistics": {"viewCount": str(100 * (i + 1)), "likeCount": "5"},
             "status": {"privacyStatus": "public"}} for i, yid in enumerate(id.split(","))]}))

    def channels(self):
        return types.SimpleNamespace(list=lambda part, mine: Esegui(
            {"items": [{"statistics": {"subscriberCount": "250"}}]}))


def test_analista_e_segretario(cartella, monkeypatch):
    import analista
    import segretario
    c.scrivi(c.PUBBLICATI, {"squali": {"youtube_id": "y1", "categoria": "squali", "visibilita": "public"},
                            "spazio": {"youtube_id": "y2", "categoria": "spazio", "visibilita": "public"}})
    monkeypatch.setattr(c, "youtube", lambda: YouTubeStatFinto())
    analista.main()
    stat = c.leggi(c.STATISTICHE, {})
    assert stat["iscritti"] == 250
    assert stat["video"]["spazio"]["visualizzazioni"] == 200
    assert stat["storico"][-1]["visualizzazioni_totali"] == 300

    monkeypatch.setattr(segretario, "REPORT", cartella / "report.md")
    segretario.main()
    testo = (cartella / "report.md").read_text(encoding="utf-8")
    assert "| Iscritti | 250 |" in testo
    assert "25%" in testo
    assert "Niente: va tutto bene" in testo


def test_segretario_segnala_problemi(cartella, monkeypatch):
    import segretario
    c.scrivi(c.PUBBLICATI, {v["id"]: {"youtube_id": "x", "visibilita": "private"}
                            for v in c.leggi(c.CONTENUTI, {})["video"]})
    testo = segretario.componi(c.leggi(c.CONTENUTI, {}), c.leggi(c.PUBBLICATI, {}), {})
    assert "privati" in testo and "quasi vuota" in testo and "Nessuna statistica" in testo

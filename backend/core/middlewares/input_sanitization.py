# backend/core/middlewares/input_sanitization.py

import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from core.logging.logger import get_logger, ctx_from_request
from core.logging.sanitize import scrub_payload

security_logger = get_logger("security.input_sanitization")


class InputSanitizationMiddleware:
    """
    Safer input sanitization middleware with:
    - Reduced false positives
    - Safe Base64 decoding (heuristic-based)
    - Configurable mode: 'block' (default) or 'log'
    - Structured logging of what triggered the detection

    Settings (optional):
        INPUT_SANITIZATION_MODE = "block"  # or "log"
        INPUT_SANITIZATION_EXCLUDED_PREFIXES = ["/insights/"]
        INPUT_SANITIZATION_BLOCK_INVALID_JSON = False  # default
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Mode: "block" (return 403) ou "log" (log uniquement, laisse passer)
        self.mode: str = getattr(settings, "INPUT_SANITIZATION_MODE", "block").lower()
        if self.mode not in {"block", "log"}:
            self.mode = "block"

        # Prefixes d’URL à exclure complètement du contrôle
        self.excluded_prefixes: List[str] = getattr(
            settings,
            "INPUT_SANITIZATION_EXCLUDED_PREFIXES",
            ["/insights/"],  # ancien comportement
        )

        # Faut-il bloquer le JSON invalide ? (sinon on laisse la view gérer ça)
        self.block_invalid_json: bool = bool(
            getattr(settings, "INPUT_SANITIZATION_BLOCK_INVALID_JSON", False)
        )

        # Patterns SQL beaucoup plus ciblés (moins de faux positifs)
        sql_patterns = [
            # SELECT ... FROM ...
            r"(?is)\bselect\b.+\bfrom\b",
            # INSERT INTO ...
            r"(?is)\binsert\b.+\binto\b",
            # UPDATE ... SET ...
            r"(?is)\bupdate\b.+\bset\b",
            # DELETE FROM ...
            r"(?is)\bdelete\b.+\bfrom\b",
            # DROP TABLE / DATABASE
            r"(?is)\bdrop\b.+\b(table|database)\b",
            # UNION [ALL] SELECT ...
            r"(?is)\bunion\b.+\bselect\b",
            # OR/AND 1=1 classique
            r"(?is)\b(or|and)\b\s+1\s*=\s*1\b",
            # WAITFOR DELAY, SLEEP, BENCHMARK
            r"(?is)\bwaitfor\s+delay\b",
            r"(?is)\bbenchmark\s*\(",
            r"(?is)\bsleep\s*\(",
            r"(?is)\bpg_sleep\s*\(",
            # Fin de requête SQL suivie d’un mot-clé dangereux
            r"(?is);\s*(drop|delete|update|insert|create|alter)\b",
        ]

        # Patterns XSS plus classiques
        xss_patterns = [
            r"(?is)<\s*script\b",
            r"(?is)<\s*iframe\b",
            r"(?is)<\s*object\b",
            r"(?is)<\s*embed\b",
            r"(?is)javascript\s*:",
            r"(?is)vbscript\s*:",
            r"(?is)\bon\w+\s*=",         # onload=, onclick=, etc.
            r"(?is)document\.",          # document.cookie, etc.
            r"(?is)eval\s*\(",
        ]

        self.sql_regex = [re.compile(p) for p in sql_patterns]
        self.xss_regex = [re.compile(p) for p in xss_patterns]

        security_logger.info(
            "InputSanitizationMiddleware initialized",
            extra={
                "mode": self.mode,
                "excluded_prefixes": self.excluded_prefixes,
                "block_invalid_json": self.block_invalid_json,
            },
        )

    # ---------- Helpers de configuration / contexte ----------

    def should_skip_sanitization(self, request: HttpRequest) -> bool:
        path = getattr(request, "path", "") or ""
        for prefix in self.excluded_prefixes:
            if path.startswith(prefix):
                return True
        return False

    # ---------- Base64 helpers (safe) ----------

    _b64_candidate_re = re.compile(r"^[A-Za-z0-9+/=]+$")

    def _is_base64_candidate(self, value: str) -> bool:
        """
        Heuristique pour éviter de décoder n’importe quoi en base64 :
        - uniquement chars de l’alphabet Base64
        - longueur multiple de 4
        - longueur minimale (évite 'Lyon' / 'Nice' etc.)
        """
        if not value or not isinstance(value, str):
            return False

        val = value.strip()
        if len(val) < 8:  # < 8 chars = on ne s’embête pas
            return False
        if len(val) % 4 != 0:
            return False
        if not self._b64_candidate_re.match(val):
            return False
        return True

    def _maybe_base64_decode(self, value: str) -> Optional[str]:
        if not self._is_base64_candidate(value):
            return None
        try:
            decoded_bytes = base64.b64decode(value, validate=True)
            decoded = decoded_bytes.decode("utf-8", errors="ignore")
            decoded = decoded.strip()
            return decoded or None
        except Exception:
            return None

    # ---------- Core detection ----------

    def _check_single_value(self, raw_value: Any) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Retourne (True, meta) si un pattern est détecté, sinon (False, None).

        meta contient :
            - type: "sql" ou "xss"
            - pattern: pattern regex qui a matché
            - value_preview: début de la valeur nettoyée
            - variant: "raw", "url_decoded", "url_decoded_twice", "base64_decoded"
        """
        if raw_value is None:
            return False, None

        try:
            value = str(raw_value)
        except Exception:
            value = repr(raw_value)

        variants: List[Tuple[str, str]] = [
            ("raw", value),
        ]

        # URL decode 1x et 2x
        try:
            url_decoded = unquote(value)
            if url_decoded != value:
                variants.append(("url_decoded", url_decoded))
                url_decoded2 = unquote(url_decoded)
                if url_decoded2 != url_decoded:
                    variants.append(("url_decoded_twice", url_decoded2))
        except Exception:
            pass

        # Base64 decode (safe heuristic)
        b64_decoded = self._maybe_base64_decode(value)
        if b64_decoded:
            variants.append(("base64_decoded", b64_decoded))

        for variant_name, v in variants:
            cleaned = re.sub(r"\s+", " ", v).strip()

            # SQL
            for pattern in self.sql_regex:
                if pattern.search(cleaned):
                    return True, {
                        "type": "sql",
                        "pattern": pattern.pattern,
                        "variant": variant_name,
                        "value_preview": cleaned[:200],
                    }

            # XSS
            for pattern in self.xss_regex:
                if pattern.search(cleaned):
                    return True, {
                        "type": "xss",
                        "pattern": pattern.pattern,
                        "variant": variant_name,
                        "value_preview": cleaned[:200],
                    }

        return False, None

    def _check_json_data(self, data: Any, path: str = "") -> Optional[Dict[str, Any]]:
        """
        Parcours récursif du JSON.
        Retourne un dict meta si quelque chose match, sinon None.
        """
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else str(key)
                res = self._check_json_data(value, new_path)
                if res:
                    res["json_path"] = new_path
                    return res
            return None

        if isinstance(data, list):
            for idx, item in enumerate(data):
                new_path = f"{path}[{idx}]"
                res = self._check_json_data(item, new_path)
                if res:
                    res["json_path"] = new_path
                    return res
            return None

        if isinstance(data, str):
            detected, meta = self._check_single_value(data)
            if detected:
                meta["json_path"] = path
                return meta

        return None

    # ---------- Logging + blocage ----------

    def _log_detection(
        self,
        request: HttpRequest,
        location: str,
        param: Optional[str],
        meta: Dict[str, Any],
        raw_value: Any,
    ) -> None:
        """
        Log structuré de ce qui a été détecté.
        """
        safe_value = scrub_payload(raw_value)

        context = ctx_from_request(request)
        context.update(
            {
                "sanitization_event": "input_detected",
                "mode": self.mode,
                "location": location,      # "query", "form", "json", etc.
                "param": param or "-",
                "detect_type": meta.get("type", "-"),
                "pattern": meta.get("pattern", "-"),
                "variant": meta.get("variant", "-"),
                "json_path": meta.get("json_path", "-"),
                "value_preview": (
                    safe_value[:200] if isinstance(safe_value, str) else str(safe_value)[:200]
                ),
            }
        )

        if self.mode == "block":
            security_logger.warning("input_sanitization_block", extra=context)
        else:
            security_logger.info("input_sanitization_log_only", extra=context)

    def _handle_detection(
        self,
        request: HttpRequest,
        location: str,
        param: Optional[str],
        meta: Dict[str, Any],
        raw_value: Any,
    ) -> Optional[HttpResponse]:
        """
        Quand on détecte quelque chose :
        - log structuré
        - soit on bloque (mode=block)
        - soit on laisse passer (mode=log)
        """
        self._log_detection(request, location, param, meta, raw_value)

        if self.mode == "block":
            return HttpResponseForbidden("Malicious content detected")
        return None  # mode log only

    # ---------- Hook Django ----------

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        if self.should_skip_sanitization(request):
            return None

        # 1) GET / query string
        if request.GET:
            for key, value in request.GET.items():
                detected, meta = self._check_single_value(key)
                if detected:
                    return self._handle_detection(request, "query_key", key, meta, key)
                detected, meta = self._check_single_value(value)
                if detected:
                    return self._handle_detection(request, "query_value", key, meta, value)

        # 2) POST/PUT/PATCH body
        if request.method in ("POST", "PUT", "PATCH"):
            ctype = (request.content_type or "").split(";")[0].strip().lower()

            # a) Form URL-encoded
            if ctype == "application/x-www-form-urlencoded":
                for key, value in request.POST.items():
                    detected, meta = self._check_single_value(key)
                    if detected:
                        return self._handle_detection(request, "form_key", key, meta, key)
                    detected, meta = self._check_single_value(value)
                    if detected:
                        return self._handle_detection(request, "form_value", key, meta, value)

            # b) JSON
            elif ctype == "application/json":
                try:
                    body_str = request.body.decode("utf-8", errors="ignore") if request.body else ""
                    if not body_str.strip():
                        return None

                    json_data = json.loads(body_str)
                except json.JSONDecodeError as e:
                    if self.block_invalid_json:
                        meta = {
                            "type": "json_decode_error",
                            "pattern": "json.loads",
                            "variant": "raw",
                            "value_preview": str(e)[:200],
                        }
                        return self._handle_detection(request, "json_decode", None, meta, body_str)
                    else:
                        security_logger.debug(
                            "Invalid JSON received, skipping sanitization",
                            extra={**ctx_from_request(request), "error": str(e)[:200]},
                        )
                        return None

                meta = self._check_json_data(json_data)
                if meta:
                    return self._handle_detection(
                        request,
                        "json",
                        meta.get("json_path"),
                        meta,
                        json_data,
                    )

        return None  # continue normal flow

    def __call__(self, request: HttpRequest) -> HttpResponse:
        early_response = self.process_request(request)
        if early_response is not None:
            return early_response
        return self.get_response(request)

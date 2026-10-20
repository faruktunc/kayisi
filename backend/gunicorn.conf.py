import os
import socket

_port = os.environ.get("PORT", "8000")


def _ipv6_available() -> bool:
    """Konteynerde IPv6 açıksa '[::]' hem IPv4 hem IPv6'yı dinler. Bu gerekli, çünkü
    'localhost' çoğu sistemde önce ::1'e çözülür ve yalnızca IPv4 dinleyen bir
    sunucuya yönlendirilen bağlantı (ör. rootless Podman) kesilir."""
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::", 0))
        return True
    except OSError:
        return False


bind = [f"[::]:{_port}"] if _ipv6_available() else [f"0.0.0.0:{_port}"]
workers = int(os.environ.get("WEB_WORKERS", "2"))
threads = int(os.environ.get("WEB_THREADS", "4"))
# Tüm desen × senaryo karşılaştırması ~30 sn sürebilir
timeout = int(os.environ.get("WEB_TIMEOUT", "300"))
accesslog = "-"
errorlog = "-"

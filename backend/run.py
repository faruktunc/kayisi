import os

# Küçük matrislerde çok iş parçacıklı BLAS hız kazandırmıyor, yalnızca CPU tüketiyor
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from app import create_app  # noqa: E402

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")

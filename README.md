# Kuru kayısı desülfitleme — proses simülatörü ve deney deseni seçimi

Ardışık H₂O₂ uygulaması + vakumlu kurutma prosesi için:

1. **Literatür tabanlı sanal kayısı simülatörü:** 6 parametre, uygulama sayısı ve hedef nem değiştirilip sonuçlar anında görülür.
2. **Deney deseni seçme yöntemi:** 30 ve üzeri deneyli aday desenler, istatistik ölçütler ve Monte Carlo simülasyonuyla karşılaştırılır.
3. **Laboratuvar deney tablosu:** Gerçek birimlerde, rastgele sıralı. CSV veya yanıt sütunları boş PDF föy olarak indirilebilir.
4. **PDF dışa aktarma:** Simülasyon raporu, desen karşılaştırma raporu ve deney föyü.

## Tak çalıştır (Docker / Podman)

Gereken tek şey Docker ya da Podman. Script, çalışan bir Docker daemon'u varsa onu, yoksa Podman'ı kullanır.

```bash
./calistir.sh              # imajı derler (ilk sefer birkaç dakika), başlatır, tarayıcıda açar → http://localhost:8080
./calistir.sh durdur       # durdurur
./calistir.sh yeniden      # kod değiştiyse imajı yeniden derleyip başlatır
./calistir.sh loglar       # sunucu loglarını izler
./calistir.sh durum        # çalışıyor mu?
PORT=9090 ./calistir.sh    # başka bir portta çalıştırır (ACMA=0 tarayıcıyı açmaz)
```

**İnternetsiz bir makineye taşımak için:**

```bash
./calistir.sh disa-aktar                                   # kayisi-simulator-image.tar.gz (~100 MB)
# Klasörü ve .tar.gz dosyasını hedef makineye kopyalayın, sonra:
./calistir.sh ice-aktar kayisi-simulator-image.tar.gz && ./calistir.sh
```

İmaj iki aşamada derlenir:
1. React arayüzü Node ile derlenir.
2. Gunicorn ile çalışan Flask, hem API'yi hem derlenmiş arayüzü tek porttan (konteyner içinde 8000) sunar.

Konteyner root olmayan bir kullanıcıyla çalışır ve sağlık kontrolü `/api/health` üzerinden yapılır. Ayarlanabilir ortam değişkenleri: `WEB_WORKERS` (2), `WEB_THREADS` (4), `WEB_TIMEOUT` (300 sn).

Windows'ta script WSL ya da Git Bash içinden çalıştırılabilir. Alternatif olarak doğrudan şu komutlar kullanılabilir:

```bash
docker build -t kayisi-simulator . && docker run -d -p 8080:8000 kayisi-simulator
```

## Geliştirme ortamı

```bash
# Backend (Flask, http://127.0.0.1:5000)
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python run.py

# Frontend (React + Vite, http://localhost:5173 — /api isteklerini backend'e yönlendirir)
cd frontend
npm install
npm run dev
```

Testler: `cd backend && .venv/bin/python -m pytest -q`

## Mimari

```
backend/
  app/
    domain/                  # İş kuralları; Flask'tan bağımsız, saf numpy
      shared/factors.py      #   6 faktör, sınırlar, kodlama (-1..+1)
      literature/model.py    #   literatür gözlemi + SO₂ kinetiği kalibrasyonu
      process/model.py       #   sanal kayısı: H₂O₂ → vakum kurutma → renk
      process/scenarios.py   #   sağlamlık senaryoları
      design/                #   desen üreteçleri (CCD, BBD, D/I-optimal, LHS), ölçütler
      evaluation/            #   RSM uyumu, desirability, optimum arama, Monte Carlo
    application/services.py  # Kullanım senaryoları (servisler)
    application/reports.py   # PDF rapor içerikleri
    infrastructure/          # JSON literatür deposu, CSV dışa aktarım
      pdf/                   #   reportlab dizgisi + matplotlib grafikleri (DejaVu font)
    interfaces/api/          # Flask blueprint'leri (REST)
    container.py             # Bağımlılıkların kurulduğu yer
  data/literature.json       # Özkan & Cemeroğlu + Uğur & Erdoğan (63 gözlem)
  tests/
frontend/                    # React tek sayfa uygulaması (sekmeler)
  src/pages/                 #   Simülatör, Desen karşılaştırma, Deney tablosu, Literatür, Varsayımlar
```

### API

| Yöntem | Yol | Açıklama |
|---|---|---|
| GET | `/api/meta` | Faktörler, yanıtlar, model parametreleri, senaryolar |
| GET | `/api/literature` | Kalibrasyon sonucu, gözlenen ve tahmin edilen değerler |
| POST | `/api/simulate` | Tek nokta simülasyonu |
| POST | `/api/simulate/sweep` | Tek faktör taraması |
| POST | `/api/simulate/optimum` | Literatür modeline göre optimum (her başlangıç SO₂ seviyesi için) |
| GET | `/api/designs` | Aday desenler |
| GET | `/api/designs/<key>` | Deney tablosu ve istatistik ölçütler |
| GET | `/api/designs/<key>/csv` | Laboratuvar tablosu (`;` ayırıcılı, Excel uyumlu) |
| GET | `/api/designs/<key>/pdf` | Deney föyü (yatay A4, yanıt sütunları boş) |
| POST | `/api/reports/simulation` | Simülasyon raporu PDF'i (`point`, `settings`, `goals`, `overrides`) |
| POST | `/api/reports/comparison` | Karşılaştırma raporu PDF'i (`{result: <evaluate yanıtı>}`; Monte Carlo yeniden çalıştırılmaz) |
| POST | `/api/evaluate` | Monte Carlo desen karşılaştırması |

POST gövdelerinde ortak alanlar şunlardır:
- `settings`: `{n_applications, target_moisture}`
- `goals`: `{so2_limit, w_so2, w_time, w_L, w_dE}`
- `overrides`: model parametrelerinin üzerine yazılacak değerler

## Model

| Bölüm | Kaynak | Model |
|---|---|---|
| H₂O₂ aşamasında SO₂ | **Literatür** (63 gözlem; azalma oranında R² ≈ 0,41, hata ±12 puan) | `SO₂ = SO₂₀·exp(−k·t)`, `ln k = ln k₀ + a·ln C + b·(T−25) − m·ln(SO₂₀/4500)` |
| H₂O₂ aşamasında su alımı | Varsayım | Doygunluk nemine üstel yaklaşım |
| Vakumlu kurutma | Varsayım | Page modeli, Arrhenius × (480/P)^β; **hedef neme kadar**, süre yanıttır |
| Kurutmada SO₂ | Varsayım | Isıl kayıp + su kaybından gelen derişme (ppm yaş baz) |
| Renk (L\*, a\*, b\*, ΔE) | Varsayım | Esmerleşme kinetiği, kalan SO₂ koruyucu etki yapar; ΔE ticari kükürtlü ürüne göre |

- Başlangıç SO₂ etkisi partinin bir özelliği olarak alınır: ardışık uygulamalarda hız sabiti değişmez.
- **Kalibrasyonun sınırı:** SO₂ ppm üzerindeki R² (~0,93) yanıltıcı derecede yüksektir; hiç azalma olmadığını varsayan model bile ~0,58 verir. Kinetiğin asıl açıklayıcılığı azalma oranındaki R²'dir (~0,41). Çalışmalar arasında hız sabiti ~3 kat fark eder (Özkan & Cemeroğlu hızlı, Uğur & Erdoğan H serisi yavaş). Simülatör ortalamayı kullanır. Bu nedenle mutlak SO₂ tahminleri, özellikle "2000 ppm'in altına inilebilir mi?" sorusu, belirsizdir.
- Vakum basıncı **mutlak basınç** olarak yorumlanmıştır. Gösterge (vakum) değeri kastediliyorsa düzeltilmelidir.
- Varsayım parametrelerinin hepsi arayüzdeki "Model varsayımları" sekmesinden değiştirilebilir.

## Desen seçme yöntemi

1. **İstatistik ölçütler** (yanıt verisi gerektirmez): D- ve G-verimliliği, ortalama tahmin varyansı, en büyük VIF, uyum eksikliği ve saf hata serbestlik dereceleri.
2. **Monte Carlo:** Her desen sanal proseste N kez uygulanır ve ölçüm hatası eklenir. Her yanıta ikinci dereceden RSM modeli uydurulur; SO₂ ve süreler isteğe bağlı olarak log dönüşümüyle modellenir.
3. **Optimum kaybı (regret):** Desirability ile bulunan "model optimumu", gerçek prosesteki istenirliğiyle değerlendirilir. Başlangıç SO₂ kontrol edilemediğinden bu, her seviye (3500 / 4500 / 5500 ppm) için ayrı hesaplanır.
4. **Sağlamlık:** Değerlendirme 5 senaryoda tekrarlanır: temel, güçlü etkileşim, zayıf vakum, renk SO₂'ye duyarlı, yüksek gürültü.
D-optimal desenlere 4 merkez tekrarı eklenir; optimal noktalar bu tekrarlar bilgi matrisine dahil edilerek seçilir. Böylece saf hata serbestlik derecesi 3 olur ve uyum eksikliği testi yapılabilir. Toplam deney sayıları 34, 40 ve 46'dır.

5. **Karar:** En iyi ortalama kayba %25 (en az 0,005) yakın desenler arasından en az deneyli olan önerilir.

Diğer çıktılar:
- **Yanlış uygun oranı:** Modelin SO₂ < limit dediği ama gerçekte limitin üstünde kalan optimumların oranı.
- **Yanıt bazında normalleştirilmiş RMSE.**

## Üçüncü taraf içerik

Arka plandaki 3D kayısı modeli (`frontend/public/models/apricot_cut.glb`):

- **"Apricot fresh and cutted off fruit with leaf"**, HQ3DMOD. Bilgi, modelle gelen `info.json` dosyasından alınmıştır; lisans bilgisi dosyada yoktur.
- Dokular `tools/optimize_gltf.py` ile 4096 px'ten 1024 px'e küçültülüp tek GLB'ye paketlenmiştir:

```bash
backend/.venv/bin/python tools/optimize_gltf.py <model.gltf> frontend/public/models/apricot_cut.glb
```

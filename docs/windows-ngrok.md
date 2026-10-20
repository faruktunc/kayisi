# Windows'ta çalıştırma ve ngrok ile paylaşma

Bu rehber uygulamayı bir Windows bilgisayarda Docker ile ayağa kaldırmayı ve ngrok ile internetten erişilebilir bir adres üzerinden paylaşmayı anlatır.

Uygulama tek bir konteynerde çalışır ve arayüz ile API aynı porttan (8080) servis edilir. Bu yüzden ngrok'a yalnızca bu tek portu açmak yeterlidir; ek ayar gerekmez.

## 1. Gerekenler

Komutları **PowerShell**'de çalıştırın. Kurulum adımları için PowerShell'i yönetici olarak açın.

| Araç | Ne için | Kurulum |
|---|---|---|
| WSL 2 | Docker Desktop'ın altyapısı | `wsl --install` (ardından bilgisayarı yeniden başlatın) |
| Docker Desktop | Konteyneri çalıştırmak | `winget install Docker.DockerDesktop` |
| Git for Windows | Repoyu indirmek ve `calistir.sh` için Git Bash | `winget install Git.Git` |
| ngrok | İnternetten erişim | `winget install Ngrok.Ngrok` ya da https://ngrok.com/download |

`winget` yoksa her aracı kendi sitesinden indirip kurabilirsiniz.

Kurulumdan sonra **Docker Desktop'ı açın** ve sol alttaki durumun "Engine running" olmasını bekleyin. Docker Desktop **Linux containers** modunda olmalıdır (varsayılan budur).

## 2. Repoyu indirme

```powershell
cd $HOME\Desktop
git clone https://github.com/faruktunc/kayisi.git
cd kayisi
```

Repo gizliyse Git sizden GitHub girişi ister.

## 3. Uygulamayı başlatma

İki yoldan birini seçin.

### Yol A: Git Bash ile (önerilen)

Klasöre sağ tıklayıp **Open Git Bash here** deyin, ya da Git Bash'te `cd ~/Desktop/kayisi` yazın. Ardından:

```bash
./calistir.sh            # ilk sefer imajı derler (birkaç dakika), başlatır ve tarayıcıyı açar
./calistir.sh durum      # çalışıyor mu?
./calistir.sh durdur     # durdurur
./calistir.sh yeniden    # kodu güncellediyseniz (git pull sonrası) yeniden derleyip başlatır
```

WSL kullanıyorsanız aynı komutlar WSL terminalinde de çalışır.

### Yol B: Yalnızca PowerShell ile

```powershell
docker build -t kayisi-simulator .
docker run -d --name kayisi-simulator -p 8080:8000 --restart unless-stopped kayisi-simulator
Start-Process http://localhost:8080
```

Durdurmak için `docker rm -f kayisi-simulator` komutunu kullanın. Kod güncellendiyse önce bu komutla durdurun, sonra yukarıdaki iki `docker` komutunu tekrar çalıştırın.

Her iki yolda da uygulama **http://localhost:8080** adresinde açılır. ngrok'a geçmeden önce yerelde açıldığından emin olun.

## 4. ngrok ile paylaşma

### Bir kerelik ayar

1. https://dashboard.ngrok.com adresinden ücretsiz bir hesap açın.
2. **Your Authtoken** sayfasındaki belirteci kopyalayıp bilgisayara tanıtın:

```powershell
ngrok config add-authtoken <BELİRTECİNİZ>
```

Belirteç gizlidir; kimseyle paylaşmayın, repoya da koymayın.

### Tüneli açma

Uygulamada **giriş/parola yok**. Adresi bilen herkes uygulamayı kullanabilir ve ağır hesapları (desen karşılaştırması ~25 sn CPU) tekrar tekrar çalıştırabilir. Bu yüzden tüneli parolayla açmanız önerilir:

```powershell
ngrok http 8080 --basic-auth "kayisi:UzunBirParola123"
```

Parola 8–128 karakter olmalıdır. Erişimi Google hesaplarıyla sınırlamak isterseniz:

```powershell
ngrok http 8080 --oauth google --oauth-allow-email ornek@gmail.com
```

Planınız bu seçenekleri desteklemiyorsa parolasız açabilirsiniz, ama adresi yalnızca güvendiğiniz kişilerle paylaşın:

```powershell
ngrok http 8080
```

ngrok çalışınca ekranda şuna benzer bir satır görünür:

```
Forwarding   https://abcd-1234.ngrok-free.app -> http://localhost:8080
```

`https://...ngrok-free.app` adresini paylaşın. PowerShell penceresi açık kaldığı sürece tünel açık kalır. Kapatmak için pencerede **Ctrl+C**'ye basın.

### Sabit adres (isteğe bağlı)

Ücretsiz adres ngrok her başladığında değişir. ngrok panelindeki **Domains** sayfasından ücretsiz bir sabit alan adı alıp her seferinde aynı adresi kullanabilirsiniz:

```powershell
ngrok http 8080 --url https://sizin-alaniniz.ngrok-free.app --basic-auth "kayisi:UzunBirParola123"
```

Eski ngrok sürümlerinde `--url` yerine `--domain sizin-alaniniz.ngrok-free.app` kullanılır.

### Ziyaretçilerin göreceği uyarı sayfası

Ücretsiz planda ziyaretçiler siteye girmeden önce ngrok'un bir uyarı sayfasını görür ve **Visit Site** düğmesine basmaları gerekir. Bu normaldir, tarayıcı başına bir kez çıkar.

## 5. Sorun giderme

| Belirti | Çözüm |
|---|---|
| `Docker kurulu ama daemon çalışmıyor` | Docker Desktop'ı açıp "Engine running" olmasını bekleyin. |
| `$'\r': command not found` (Git Bash) | Script Windows satır sonlarıyla inmiş. Git Bash'te `sed -i 's/\r$//' calistir.sh` çalıştırın ya da repoyu yeniden klonlayın (repo `.gitattributes` ile LF'yi zorunlu kılar). |
| `Port 8080 kullanımda` | Başka bir port kullanın: Git Bash'te `PORT=9090 ./calistir.sh`, ngrok'ta `ngrok http 9090`. Yol B'de `-p 9090:8000` yazın. |
| `localhost:8080` açılmıyor | `docker ps` ile konteyner çalışıyor mu bakın; loglar için `docker logs kayisi-simulator`. |
| ngrok `ERR_NGROK_4018` / authtoken hatası | `ngrok config add-authtoken` adımını tekrarlayın. |
| ngrok adresi `502 Bad Gateway` veriyor | Uygulama çalışmıyor ya da ngrok yanlış porta yönlendiriliyor; önce `http://localhost:8080` adresini yerelde kontrol edin. |
| İlk derleme çok uzun sürüyor | Normal: Node ve Python bağımlılıkları indirilir. Sonraki başlatmalar saniyeler sürer. |

## 6. Güncelleme

```bash
git pull
./calistir.sh yeniden
```

ngrok'u yeniden başlatmanız gerekmez. Konteyner yeniden başladıktan sonra aynı tünel çalışmaya devam eder.

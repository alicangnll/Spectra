# Geliştirme Kılavuzu

> Eğer bir kodlama aracısıysanız, lütfen bunun yerine [AGENTS.md](AGENTS.md) dosyasını okuyun.

Bu belge insan katkıda bulunanlar içindir. Geliştirme ortamının nasıl kurulacağını, dal iş akışını ve bir PR açmadan önce yapılacakları kapsar.

---

## Ön Koşullar

- **Binary Ninja** (build 3164 veya daha yenisi) ve/veya **IDA Pro 9.x**
- **Python 3.10–3.11** önerilir (IDA Pro + Python sürümleri hakkında aşağıdaki nota bakın)
- **Git**
- Desteklenen en az bir LLM sağlayıcısı için API anahtarı (Anthropic, OpenAI, Google veya yerel bir Ollama örneği)

> **IDA Pro notu:** Python 3.10 en güvenli seçenektir. Daha yüksek sürümler Qt sinyal dağıtımı sırasında bir Shiboken UAF çökmesine neden olabilir. Ayrıntılar için AGENTS.md dosyasının IDA API Notları bölümüne bakın.

---

## Kurulum (Geliştirme)

Repoyu klonlayın ve değişikliklerin bir sonraki başlatmada yeniden yükleme olmadan etkili olması için host'un eklenti dizinine symlink oluşturun.

**Binary Ninja**
```bash
# macOS
git clone https://github.com/alicangnll/Spectra
ln -s "$(pwd)/spectra" ~/Library/Application\ Support/Binary\ Ninja/plugins/spectra

# Linux
git clone https://github.com/alicangnll/Spectra
ln -s "$(pwd)/spectra" ~/.binaryninja/plugins/spectra

# Windows (Yönetici olarak çalıştırın)
git clone https://github.com/alicangnll/Spectra
mklink /D "%APPDATA%\Binary Ninja\plugins\spectra" "<klonlanmış repo için tam yol>"
```

**IDA Pro**
```bash
# macOS / Linux
ln -s "$(pwd)/spectra" ~/.idapro/plugins/spectra

# Windows
mklink /D "%APPDATA%\Hex-Rays\IDA Pro\plugins\spectra" "<klonlanmış repo için tam yol>"
```

---

## Python Bağımlılıkları

Çalışma zamanı bağımlılıklarını host'un kullandığı Python ortamına yükleyin:

```bash
pip install anthropic>=0.39.0 openai>=1.50.0 google-genai>=1.0.0 tomli>=2.0.0
```

Geliştirme araçları için (CI kontrolleri, yerel test çalıştırma):

```bash
pip install ruff mypy pytest desloppify
```

---

## Dal İş Akışı

```
feat/my-thing  ─┐
fix/some-bug   ─┤──► dev ──► main
chore/deps     ─┘
```

1. `dev` dalından açıklayıcı bir önek kullanarak ayrılın:
   - `feat/` — yeni özellik
   - `fix/` — hata düzeltmesi
   - `refactor/` — kod yeniden yapılandırma, davranış değişikliği yok
   - `chore/` — bağımlılıklar, araçlar, dokümantasyon
2. Değişikliklerinizi küçük, odaklanmış commitlerle yapın
3. İtmek önce yerel CI betiğini çalıştırın (aşağıya bakın)
4. `dev`'i hedefleyen bir PR açın
5. İncelendikten ve CI geçtikten sonra (`./ci-local.sh` çalıştırın; Actions iş akışı manuel-only) `dev`'e birleştirilir
6. Yayınlar `dev` → `main` şeklinde bir sürüm etiketiyle gider

**`main`'e doğrudan itmeye izin verilmez** — PR üzerinden gitmelidir. `dev` doğrudan itmeleri kabul eder.

---

## İtmek Önce — Yerel CI Kontrolü

Her özellik veya düzeltmeden sonra, PR açmadan önce bu betiği çalıştırın:

```bash
./ci-local.sh
```

Bu, GitHub Actions iş akışının çalıştırdıklarının aynısını yansıtır. Biçimlendirme hatalarını, lint sorunlarını, tip hatalarını, test başarısızlıklarını ve kod kalitesi gerilemelerini yakalar.

**GitHub Actions CI yalnızca manuel çalışır** — push veya PR'de tetiklenmez.
Bu betik her commit için birincil kontrol kapısıdır. Uzak iş akışını
istediğinizde çalıştırın: **Actions → CI → "Run workflow"**, veya:

```bash
gh workflow run ci.yml
```

Ruff biçimlendirme sorunları bildirirse, otomatik düzeltin:

```bash
./ci-local.sh --fix
```

Betik, `ruff` ve `mypy` zaten mevcut değilse yükler. Araçları eksik olan adımları atlar, sert bir şekilde başarısız olmaz, bu yüzden kısmi bir ortamda çalıştırmak güvenlidir.

---

## Testleri Çalıştırma

```bash
python3 -m pytest tests/ -v
```

Testler `tests/` altında alt sisteme göre organize edilmiştir:

```
tests/
├── agent/       # Agent döngüsü, plan modu, keşif, oturum
├── core/        # Config, sanitize, hatalar, profil, logging
│                # + xref, function_naming, type_recovery, bookmark, advanced_search (v1.2.5+)
├── providers/   # Tüm LLM sağlayıcıları
├── tools/       # Tool implementasyonları (binja, IDA, shared)
└── mocks/       # ida_mock — IDA dışında test için IDA Pro API'sini taklit eder
```

Binary Ninja ve IDA Pro API'leri test sırasında taklit edilir — test paketini çalıştırmak için host yüklemenize gerek yoktur.

### Test paketi tuzakları (zor yoldan öğrenildi)

- **Paylaşılan IDA mock'ları, import sırasında birkaç test modülü tarafından
  yeniden kurulur** — `sys.modules`'ta son `install_ida_mocks()` çağrısı
  kazanır. Daha önce içe aktarılan bir modül hâlâ *eski* mock nesnelerini
  tutar. Testiniz doğrudan `sys.modules["idautils"]` yapılandırırsa,
  test edilen modülün hiç kullanmadığı bir mock'a yama yapmış
  olabilirsiniz (belirti: tek başına geçer, tam pakette başarısız olur).
  Ya modülün kendi bağlantılarını yapılandırın
  (`spectra_module.idautils`) ya da `setUpModule` içinde
  `importlib.reload()` edin (bkz. `tests/tools/test_ssl_pinning.py`).
- **`spectra.core.config` bazı testler tarafından** `MagicMock` ile
  stub'lanır. Gerçek config kaydet/yükle davranışını iddia eden her şey
  bir **alt süreçte** çalışmalıdır (`[sys.executable, "-c", script,
  repo_root]` — bkz. `tests/tools/test_adb.py` içinde
  `TestConfigRoundTrip`). Güvenlik yardımcıları da `val is True` ile
  kapalı başarısız olur; böylece mock'lanmış bir config asla güvensiz
  komut iznini etkinleştiremez.
- **Bağlamalar arasında `Signal` ve `QTimer.singleShot`**: düz bir Python
  işçi iş parçacığından planlanan `QTimer.singleShot` asla tetiklenmez
  (olay döngüsü yoktur). İşçi→UI iletişimi `Signal(...).emit`
  (kuyruklanan bağlantı) kullanmalıdır; bu PySide6, PyQt5 ve PyQt6'da
  aynı şekilde çalışır.

---

## Kod Kalitesi

Bu proje kod tabanı sağlığını takip etmek için [desloppify](https://github.com/peteromallet/desloppify) kullanır. Mevcut amaç puanı **89.0/100** (hedef: 95).

### Son İyileştirmeler (v1.2.5+)

**Araç Parametre Doğrulama:**
- Tool çalıştırmadan önce gerekli parametrelerin otomatik doğrulaması eklendi
- Gizemli TypeErrors yerine eksik parametreler için net hata mesajları
- `spectra/tools/registry.py` içinde implement edildi

**Windows Otomatik Kurulum:**
- Windows kullanıcıları için otomatik `anthropic` paketi kurulumu eklendi
- IDA'nın Python'u bulunamadığında sistem Python'a geri dönüş
- `spectra_plugin.py` içinde implement edildi

Herhangi bir zamanda yerel bir tarama çalıştırın:

```bash
desloppify scan
desloppify status   # puan dashboard'u
desloppify issues   # bulgular iş kuyruğu
```

`desloppify review` komutu (öznitelikli puanlama) bir LLM kullanır ve her değişiklikte değil, yayınlardan önce manuel olarak çalıştırılır.

**Python sürüm notu:** desloppify'ın AST tabanlı dedektörleri taramayı çalıştıran Python sürümüne duyarlıdır. GitHub Actions Python 3.11 kullanır (~89.4 puan). Farklı yerel sürümler hafifçe farklı puanlar verecektir — 0.5 puanlık temel fark bu varyansı absorbe etmek için bilinçlidir. Tutarlı yerel sonuçlar için `uv` yükleyin; repo kökündeki `.python-version` dosyası 3.11'e sabitlenir ve `ci-local.sh` bunu otomatik kullanacaktır.

```bash
pip install uv                   # uv'u bir kez yükleyin
uv add desloppify --dev          # desloppify ekleyin (ci-local.sh bunu otomatik yapar)
```

---

## Commit Stili

```
feat(agent): plan modu için akış iptali ekle
fix(binja): imleçteki eksik fonksiyonu nazikçe ele al
refactor(providers): yeniden deneme mantığını temel sınıfa ayıkla
security: sanitize.py içinde homoglif dizilerini temizle
docs: AGENTS.md içinde tool kayıt kılavuzunu güncelle
```

Biçim: `type(scope): kısa açıklama`
- Commit başına mantıksal bir değişiklik
- Kapsam alt sistemdir: `agent`, `binja`, `ida`, `ui`, `providers`, `mcp`, `skills`, `core`

---

## Yayın Süreci

1. PR üzerinden `dev` → `main` birleştir
2. `plugin.json` içinde `version`'u yükselt
3. Etiketle ve it:
   ```bash
   git tag v0.x.x
   git push origin v0.x.x
   ```
4. GitHub Actions etiketin `plugin.json` ile eşleştiğini doğrular ve GitHub Release'ı yayınlar
5. Binary Ninja eklenti yöneticisi yeni sürümü `main`'den otomatik alır

---

## Yardım Alma

- İçler, mimari kararlar ve kodlama kuralları hakkında derin teknik dokümantasyon için [AGENTS.md](AGENTS.md) okuyun
- https://github.com/alicangnll/Spectra/issues adresinde issue açın

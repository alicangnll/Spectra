# Spectra için Windows ARM64 Uyumluluk Düzeltmesi

## Sorun

Windows ARM64 sistemlerde IDA Pro, öykünme altında x64 uygulaması olarak çalışır. Windows ARM64 üzerinde varsayılan Python kurulumu ARM64-native'dir ve bu durum derlenmiş Python uzantıları (`.pyd` dosyaları) için bir mimari uyumsuzluğu oluşturur.

Spectra `anthropic` modülünü içe aktarmaya çalıştığında şu hatayla başarısız olur:
```
No module named 'pydantic_core._pydantic_core'
```

Bu durum `pydantic_core`'un mimariye özgü derlenmiş modüller içermesinden kaynaklanır.

## Çözüm

ARM64 Python'un yanı sıra **x64 Python** yükleyin ve IDA Pro için x64 Python paketlerini kullanın.

## Adımlar

### 1. x64 Python Yükleyin

1. x64 Python yükleyicisini https://www.python.org/downloads/windows/ adresinden indirin
   - "Windows installer (64-bit)" seçeneğini arayın
   - ARM64 sürümü **DEĞİL**

2. Yükleme sırasında:
   - "Customize installation" seçeneğini seçin
   - Yükleme konumu: `C:\Program Files\Python313` (veya benzeri)
   - "Add Python to PATH" işaretleyin

### 2. ARM64 Düzeltme Betiğini Çalıştırın

```cmd
cd C:\path\to\Spectra
install_windows_arm64_fix.bat
```

Bu betik şunları yapar:
- x64 Python kurulumlarını algılar
- x64 Python kullanarak tüm Spectra bağımlılıklarını yükler
- Derlenmiş paketleri Spectra eklenti dizinine kopyalar

### 3. Manuel Alternatif

Betik çalışmazsa, paketleri manuel olarak kopyalayın:

```cmd
:: x64 Python site-packages konumunu bulun
C:\Program Files\Python313\python.exe -c "import site; print(site.getsitepackages()[0])"

:: Paketleri Spectra'ya kopyalayın
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\anthropic" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\anthropic\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\pydantic" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\pydantic\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\pydantic_core" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\pydantic_core\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\httpx" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\httpx\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\httpcore" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\httpcore\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\anyio" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\anyio\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\sniffio" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\sniffio\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\certifi" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\certifi\"
xcopy /E /I /Y "C:\Program Files\Python313\Lib\site-packages\idna" "C:\Users\YOURUSER\.idapro\plugins\spectra\lib\idna\"
```

`YOURUSER` kısmını gerçek kullanıcı adınızla değiştirin ve gerektiğinde yolları ayarlayın.

### 4. Doğrulayın

1. IDA Pro'yu yeniden başlatın
2. Çıktı penceresinde şu mesajları arayın:
   ```
   [Spectra] Added lib directory: C:\Users\...\plugins\spectra\lib
   [Spectra] anthropic found
   ```

3. Spectra'yı açmak için `Ctrl+Shift+I` tuşlarına basın
4. Ayarlar kısmında API anahtarınızı yapılandırın
5. Basit bir sorguyla test edin

## Nasıl Çalışır

Güncellenmiş `spectra_plugin.py` artık:

1. **Önce** spectra paketinin yanında bir `lib` alt dizinini arar
2. **En yüksek öncelikle** bunu `sys.path`'e ekler
3. **Gerekirse** sistem Python yollarına geri döner

### Otomatik Anthropic Kurulumu (v1.2.5+)

v1.2.5 sürümünden itibaren Spectra, Windows kullanıcıları için **otomatik bağımlılık kurulumu** içerir:

- Eklenti yüklendiğinde `anthropic` kullanılabilir olup olmadığını kontrol eder
- Eksikse, otomatik olarak kurmayı dener:
  1. IDA'nın paketlenmiş Python'u (kullanılabilirse)
  2. IDA sürümüyle eşleşen sistem Python'u (örn. Python 3.10)
  3. `C:\Program Files\Python310\` konumundaki x64 Python (ARM64 yerine tercih edilir)

Bu mimari, sistem Python'u ARM64 olsa bile Spectra'nın x64-derlenmiş paketleri kullanmasına izin verir.

### Log Mesajları

Otomatik kurulum çalıştırıldığında şunları göreceksiniz:

```
[Spectra] WARNING: anthropic not found: No module named 'anthropic'
[Spectra] Attempting auto-install...
[Spectra] Installing anthropic with Python: C:\Program Files\Python310\python.exe
[Spectra] anthropic installed successfully
```

Otomatik kurulum başarısız olursa şunları göreceksiniz:

```
[Spectra] Warning: Could not find Python executable
[Spectra] Please install manually: python -m pip install anthropic>=0.39.0
```

## Sorun Giderme

**"No module named 'pydantic_core._pydantic_core'" hatası devam ediyorsa:**
- Paketleri x64 Python'dan (Program Files) kopyaladığınızı, ARM64 Python'dan (AppData) olmadığını doğrulayın
- `lib\pydantic_core` içindeki `.pyd` dosyalarının x64, ARM64 değil olduğundan emin olun

**IDA başlangıçta çöküyorsa:**
- Tüm `.pyd` dosyalarının x64 mimarisinde olduğunu kontrol edin
- `lib` dizinini kaldırın ve doğru paketlerle tekrar deneyin

**x64 Python bulunamıyorsa:**
- python.org adresinden indirip yükleyin
- x64 sürümünü seçtiğinizden, ARM64 olmadığından emin olun

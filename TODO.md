# Spectra — TODO & Aşama Planı

Bu dosya, devam eden işin aşamalarını, planları ve durumu izler.
Sürüm tek kaynağı: [`update.json`](update.json) (şu an **1.4.0**, 2026-08-17).

Durum simgeleri: ✅ tamam · 🔶 kısmen tamam / doğrulama bekliyor · ⬜ planlandı

---

## Tamamlanan Aşamalar (2026-08-17 iterasyonu)

### Aşama 1 — Update akışındaki donma ✅

**Belirti:** Settings → Update sekmesi "Downloading update: 1.6 MB" adımında
sonsuz derecede takılıyordu.

**Kök neden:** Worker iş parçacığından `QTimer.singleShot(0, lambda: ...)`
planlanıyordu. O iş parçacığında Qt olay döngüsü olmadığı için zamanlayıcı
hiç tetiklenmiyor ve UI güncellemeleri sessizce düşüyordu. (Üç bağlamada
doğrulandı: PySide6'ta lambda ile hiç çalışmaz, PyQt5/6'da yalnızca bound
method çalışır — güvenilir olmayan bir fark.)

**Yapılanlar:**
- `UpdateSignals` sinyal sınıfına `check_result` / `install_result`
  eklendi; denetim ve kurulum akışları artık yalnızca
  `Signal(object).emit` ile rapor veriyor (kuyruklanan bağlantı → ana iş
  parçacığı; her bağlamada çalışır).
- Tüm güncelleme slot'larına `if self._closed: return` koruması; başarı
  sonrası sürüm etiketi tazeleniyor.
- İndirme chunk boyutu 8 KB → 64 KB.

**Dosyalar:** `spectra/ui/settings_dialog.py`, `spectra/core/updater.py`

### Aşama 2 — Tüm modüller için güvensiz komut izni ✅

**İstek:** IDA içinde `adb_shell` sürekli
"Command not allowed for safety: Command 'curl' not in safe list" veriyordu.
Settings'e, tehlikeli komutlara izin veren tek bir checkbox eklendi ve bu
izin **tüm modüller** için geçerli.

**Yapılanlar:**
- Yeni `spectra/core/safety.py` — `unsafe_commands_allowed()` tek doğruluk
  kaynağı; config'i her çağrıda diskten okur (yeniden başlatma gerektirmez),
  `val is True` ile **kapalı başarısız** olur (mock/bozuk config asla izni
  açamaz).
- `spectra/core/config.py` — `allow_unsafe_commands: bool = False` alanı +
  load() izin listesi.
- Geçit güncellemeleri:
  - `spectra/tools/adb.py` — `_check_shell_command_safety` erken izin
    (güvenli liste + tehlikeli kalıp regexleri aşıldığında uyarı log'lar).
  - `spectra/tools/script_guard.py` — AST denetimi VE yerleşikler
    kısıtlaması izinle kalkar.
  - `spectra/core/tool_infrastructure.py` — `ToolSafety`
    komut/ağ denetimleri erken izin döner.
- Settings → Behavior → **"Allow unsafe commands (all tools)"** checkbox'ı.
- **Bilinçli olarak kapsam dışı:** MCP yol/argüman doğrulaması
  (`mcp/security.py`), isteme enjeksiyonu temizleme, fuzzing süre/bellek
  sınırları (kaynak koruması).

**Testler:** `tests/tools/test_adb.py` (config round-trip alt süreçte),
`tests/core/test_safety_bypass.py`, `tests/tools/test_script_guard.py`
genişletmesi.

### Aşama 3 — Yapısal SSL sabitleme tespiti ✅

**İstek:** `detect_ssl_pinning_impl` hiçbir şey bulmuyordu; standart
kalıplar yerine **koddan kendisi bulmalı**.

**Kök neden (eski kodda):**
1. Java/Swift kaynak-kod kalıpları (`CertificatePinner.builder`,
   `didReceiveChallenge`) yerel söküm metniyle eşleştiriliyordu — asla
   tutmaz.
2. Dizgi taraması segment filtresi `.rodata` dışlıyordu (sabit veriler
   çoğunlukla oradadır).
3. `CERT_PATTERNS` tanımlı ama hiç kullanılmıyordu (ölü kod).

**Yeni motor** (`spectra/tools/ssl_pinning.py`):
- **Toplayıcılar** (IDA: `idautils.Names`/`XrefsTo`/`Strings`; Binja:
  `bv.symbols`/`get_code_refs`/`get_strings`) ham yapısal bilgiler toplar;
  her API çağrısı ayrıca try/except korumalı.
- **Saf çözümleyici** `analyze_pinning_facts(...)` — sökümleyici API'si
  içe aktarmaz, birim test edilebilir:
  - doğrulama içe aktarmaları (OpenSSL/BoringSSL, SecTrust, Schannel,
    WinHTTP, curl) — Mach-O `_` ve ELF `@version` normalizasyonlu
  - çağıranlar → **hook/patch hedefleri** (adresli)
  - ikilinin kendi sembolleri → yerel trust-manager mantığı
    (`checkServerTrusted`, `getAcceptedIssuers`, `okhostnameverify`, JNI
    `j_` export'ları; `sub_` vb. otomatik adlar hariç)
  - pin malzemesi (tüm segmentlerde): OkHttp `sha256/…`, gömülü PEM,
    HPKP `pin-sha256`, 40/64-hex anahtar özeti
  - güven destekli karar: YÜKSEK / ORTA / DÜŞÜK / yok
- **Sözleşme korundu:** sonuç sözlüğü anahtarları (`frameworks` dahil) ve
  `SSL_PINNING_PATTERNS` bypass kataloğu → IDA/Binja `get_ssl_bypass`
  olduğu gibi çalışır. Kataloğa `sectrust` (iOS/macOS) eklendi.

**Testler:** `tests/tools/test_ssl_pinning.py` — 39 test: sınıflandırma,
sembol eşleme, karar eşiği mantığı, rapor formatı, mock'lu IDA toplayıcısı,
sahte BinaryView ile Binja toplayıcısı, hata yutma davranışı.

### Aşama 7 — iOS cihaz araçları (ADB muadili) ✅

**İstek:** IDA Pro ve Binary Ninja için, Android ADB aracının iOS
telefonlar için benzeri.

**Yapılanlar:**
- Yeni `spectra/tools/ios.py` — libimobiledevice sarmalayıcısı, ADB
  araçlarıyla aynı yapıda (singleton yönetici, alt süreç tabanlı, tüm
  araçlar string döner):
  - `ios_check`, `ios_pair`, `ios_connect`, `ios_info` (lockdown),
  - `ios_syslog` (süre sınırlı yakalama + son N satır),
  - `ios_list_apps` / `ios_app_info` (plist XML ayrıştırma + metin
    geri düşüşü), `ios_install` / `ios_uninstall`,
  - `ios_screenshot`, `ios_pull_crash_reports`, `ios_backup`,
  - `ios_jailbreak_check` (iproxy yönlendirmeli SSH port yoklaması),
  - `ios_shell` — jailbreak'li cihazda SSH (varsayılan
    `root@127.0.0.1:2222`, `sshpass` ile parola); **güvenlik geçidi
    adb_shell ile birebir aynı** (güvenli önekler + salt-okunur
    `dpkg -l`/`plutil -p` + iOS'a özgü tehlikeli kalıplar:
    `reboot`, `dpkg -i`, `killall`, `passwd`, `nvram`, … ve Settings
    `allow_unsafe_commands` izni).
- Binary keşfi PATH + Homebrew/ /usr/local/ /opt/local dizinleri;
  eksik araçta kurulım komutunu söyleyen hata mesajı.
- Kayıt: her iki kayıt defterine (`spectra/ida/tools/registry.py`,
  `spectra/binja/tools/registry.py`) `register_module(ios)` eklendi —
  IDA ve Binary Ninja'da aynı araç seti.
- Yan düzeltme: `adb.py` ve `ios.py` tehlikeli kalıbındaki
  `-\rf` yazım hatası (`\r` = satır başı karakteri, kalıp asla
  tutmuyordu) `-[a-z]*r[a-z]*f` olarak düzeltildi; `rm .../` kalıbı
  zaten yakaladığı için testler etkilenmedi.

**Testler:** `tests/tools/test_ios.py` — 20 test: geçit varsayılanları,
bypass, binary keşfi, `_require` hata mesajı, UDID çözümleme, kapalı port
jailbreak yoklaması, kayıt defteri tam araç seti.

**Dokümantasyon:** `docs/USAGE.md` §13.4 tablo satırı + yeni §13.6,
`docs/ARCHITECTURE.md` geçit listesi, README'ler (EN+TR karşılıkları).

### Aşama 8 — CI manuel tetikleme + install.sh'e iOS araçları ✅

**İstek:** (1) CI her GitHub commit'inde çalışmasın, yalnızca elle
başlatılsın; (2) libimobiledevice Linux'ta ve macOS'ta install.sh ile
kurulsun; install.sh her iki platformla uyumlu olsun.

**Yapılanlar:**
- `.github/workflows/ci.yml` — `on: push/pull_request` kaldırıldı,
  yalnızca `on: workflow_dispatch` bırakıldı. Çalıştırma: Actions → CI →
  "Run workflow" veya `gh workflow run ci.yml`. Birincil kapı yerel
  `./ci-local.sh` (aynı kontrolleri çalıştırır).
- `install.sh` — yeni `install_libimobiledevice()`:
  - macOS: Homebrew (`brew install libimobiledevice`; Homebrew yoksa
    uyarı + atlama, ölümcül değil),
  - Linux: apt (`libimobiledevice-utils usbmuxd`) / dnf / pacman / zypper
    (`libimobiledevice-tools usbmuxd`); systemd'de usbmuxd best-effort
    `enable --now`,
  - zaten kuruluysa erken dönüş; root ise sudo kullanmama; kurulum
    başarısızlığı kurulumu asla durdurmaz (ios_* araçları eyleme
    dönüştürülebilir hata mesajı verir).
  - Yeni `--no-ios` bayrağı + `--help`/başlık dokümantasyonu.
  - Doğrulandı: `bash -n`, `--help` çıktısı, erken-dönüş dalı (sahte
    `idevice_id`) ve Homebrew-yok dalı (RC=0).

**Dokümantasyon:** DEVELOPMENT (EN+TR) "GitHub Actions CI manual-only"
notu + `gh workflow run` örneği; README'ler (EN+TR) kurulum bloğuna iOS
araç notu; USAGE §13.6 (EN+TR) kurulum cümlesi install.sh'e güncellendi.

### Aşama 9 — Updater sağlamlaştırma + başlangıç kontrolü + kaydet-yeniden başlat ✅

**Tetikleyici:** Kullanıcı "Updater böyle kaldı" bildirimi + üç yeni istek:
(1) eklenti açılışında update kontrolü, (2) update sonrası IDB'yi kaydedip
IDA'yı yeniden başlatma seçeneği, (3) harici komut bağımlılığının kaldırılması.

**Log analizi (dün gece 00:22 koşusu):** akış aslında 2.3 saniyede tamamlanmış
(indir → kur → "Update installed successfully"); UI'da takılı görünen durum
sinyalin işlendiği anlama gelmiyordu. Yine de kodda üç sınırsız bekleme
noktası vardı — kapatıldı:

**Yapılanlar (`spectra/core/updater.py`):**
- İndirme: soket timeout 300s → 60s + **600 saniyelik toplam son tarih**;
  takılan indirme mutlaka log'lu hatayla sonuçlanır, yarım dosya silinir.
- `tar` subprocess → **stdlib `tarfile`** (backup/restore): hiçbir OS'ta
  harici `tar` binary'si gerekmez (Windows dahil). Python < 3.12 için
  `filter="data"` geri düşüşü.
- Yedek dizini CWD-göreli `.spectra_backup` yerine kullanıcı config dizini
  altına (`_backup_root()`) — yedekler IDA'nın çalışma dizinine saçılmaz.
- Üç kez tekrarlanan kurulum-dizini çözümlemesi tek `_install_root()` metodunda.
- Yeni `check_and_notify()` — plugin init'ten çağrılabilen daemon-thread
  başlangıç kontrolü.
- `git pull` hızlı yolu isteğe bağlı kalır (git yoksa saf-Python zip yoluna
  düşer — bağımlılık yok).

**Yapılanlar (`spectra_plugin.py`):** `init()` artık arka planda update
kontrolü yapar; yeni sürüm varsa Output penceresine
"Update available: a → b (Settings → Update)" yazar (worker thread'den
`ida_kernwin.execute_sync` ile ana iş parçacığına taşınır).

**Yapılanlar (`spectra/core/host.py`):** `save_host_database()` (IDB/BNDB
kaydet) ve `restart_host()` (IDA çalıştırılabilirini `sys.argv[0]`/idaapi
konumundan bulur, aynı IDB ile yeniden başlatır, `qexit` — shell komutu yok).

**Yapılanlar (`spectra/ui/settings_dialog.py`):** kurulum başarılı olunca
"Save the database and restart IDA Pro now?" sorusu — Evet: IDB'yi kaydet +
IDA'yı aynı veritabanıyla yeniden başlat; binary bulunamazsa manuel restart
önerisi.

**Testler:** `tests/core/test_updater.py` 15 → 23 test: indirme son tarihi
iptali + yarım dosya temizliği, yedek kök dizini CWD-bağımsızlığı,
tarfile backup↔restore turu, başlangıç kontrolü worker'ı (bildirim /
güncel / hata yutma).

### Aşama 10 — rikugan → spectra iz temizliği ✅

**İstek:** "rikugan adındaki her şeyi spectra olarak değiştir, izi bile
kalmayacak — sadece 'Forked from Rikugan' kalacak."

- Dosya yeniden adları (kullanıcı commit'i `9a0f9b2`):
  `tests/tools/test_rikugan_*.py` → `test_spectra_*.py`,
  `tests/fixtures/RIKUGAN.md` → `SPECTRA.md`, `docs_tr/RIKUGAN.md` → `SPECTRA.md`.
- `install.sh`: `RIKUGAN_BRANCH` → `SPECTRA_BRANCH` (3 yer).
- `install.ps1`: `RIKUGAN_DIR`/`RIKUGAN_BRANCH` → `SPECTRA_DIR`/`SPECTRA_BRANCH`.
- `uninstall.ps1`: `RIKUGAN_DIR` → `SPECTRA_DIR`.
- `README.md` + `docs_tr/README.md`: karşılaştırma bölümleri "Upstream"/
  "Temel Proje" olarak yeniden adlandırıldı, Teşekkürler listesindeki madde
  kaldırıldı.
- Kalan tek iz — bilinçli atıf: README.md 7+17, docs_tr/README.md 7+17,
  docs/README.md 7 ("Forked from Rikugan" satırları; `grep -ri rikugan`
  çıktısı yalnızca bunlar).

### Aşama 11 — Dosya düzeyi analiz araç ailesi (11 yeni araç) ✅

**İstek:** "Başka sence ne tarz toolar ekleyebiliriz" → orta efor / yüksek
getiri + hızlı kazanım paketleri onaylandı; dağıtım sırasında düşen
`fingerprint_libs` "düzelt" emriyle tamamlandı.

**Temel:** `spectra/tools/binary_format.py` — saf-Python ELF/PE/Mach-O
(fat dahil) çözümleyici (yalnızca stdlib; bölüm/sembol/içe aktarma/overlay
raporu). Testler sentetik `struct.pack` ikilileri üretir (gerçek dosya yok,
her platformda aynı sonuç). Ailedeki her araç bu çözümleyicinin ya da ham
bayt taramasının üzerine kuruludur — **hiçbir OS komutu çağırmaz**.

**Araçlar** (hepsi saf çözümleyici + markdown biçimlendirici + ince
`@tool`; host'a bağımsız, IDA + Binja kayıt defterlerine
`register_module()` döngüsüyle bağlı; IDA 146 / Binja 148 araç):

| Modül | Araç(lar) | Test |
|---|---|---|
| `checksec.py` | `checksec` — PIE/NX/RELRO/canary/FORTIFY/CFG/imza + sömürü etkisi | 9 |
| `entropy.py` | `entropy_report` — bölüm entropisi + UPX/Themida/VMProtect parmak izi | 8 |
| `binary_format.py` | (temel — aracı yok) | 15 |
| `binary_diff.py` | `binary_diff` — sembol düzeyi fark, değişen bayta göre sıralı | 25 |
| `crypto_detect.py` | `detect_crypto` — AES/DES/RC4/MD5/SHA tabloları, RSA/ECC sabitleri | 55* |
| `ioc_collector.py` | `collect_iocs` — IP/domain/URL/mutex/regkey/cüzdan, masumlaştırılmış | ↑ |
| `str_decode.py` | `decode_string`, `find_stack_strings` — hex/b64/rot/XOR + yığın-string | 48 |
| `yara_tools.py` | `yara_generate`, `yara_scan` — kural üret + tara (`yara-python` isteğe bağlı) | 56** |
| `file_meta.py` | `file_meta` — MD5/SHA256/imphash/PDB yolu/Go build bilgisi | ↑ |
| `fingerprint_libs.py` | `fingerprint_libs` — statik kütüphane sürümleri ("OpenSSL 1.0.2k-fips"…) | 22 |

\* crypto+IOC toplam · \*\* yara+file_meta toplam (+5 skip: yara-python kurulu değil)

**Süreç:** 4 paralel arka plan agent'ı (A: binary_diff, B: crypto+IOC,
C: str_decode, D: yara+file_meta) + benim modüllerim (binary_format,
checksec, entropy, fingerprint_libs). Her agent çıktısı benim tarafımdan
bağımsız yeniden doğrulandı (pytest + ruff + `_tool_definition` kontrolü).

**Dokümantasyon:** USAGE §13.8 (EN+TR) araç tablosuyla, README'ler (EN+TR)
özellik maddesi, ARCHITECTURE (EN+TR) "File-Level Analysis Tools" bölümü.



| Kontrol | Sonuç |
|---------|-------|
| `pytest tests/ -q` | ✅ 1509 geçti, 13 atlandı (aşama 10 sonrası 1271/8; +238 test: araç ailesi) |
| `ruff check spectra/ tests/ spectra_plugin.py` | ✅ temiz |
| `mypy spectra/core spectra/providers` | ✅ main ile aynı (1 önceden mevcut hata: kök `__init__.py` çift modül adı) |
| Kayıt defteri duman testi (IDA + Binja) | ✅ 11 yeni aracın tümü kayıtlı (146/148 araç) |
| `bash -n install.sh` + `--help` | ✅ `SPECTRA_BRANCH=main` |
| `grep -ri rikugan` (iz temizliği) | ✅ yalnızca 5 bilinçli atıf satırı |
| IDA Pro üzerinde manuel SSL tespit denemesi | 🔶 gerçek ikili üzerinde kullanıcı doğrulaması bekleniyor |
| Update akışının uçtan uca denemesi (GitHub üzerinden) | 🔸 gerçek indirme kullanıcıda doğrulanacak |

### Aşama 12 — Sohbet geçmişi yüklenince panelin boş kalması ✅

**Belirti:** IDA içinde panel açıldığında (veya veritabanı değiştiğinde) oturum
geçmişi geri yükleniyor ama sohbet alanı siyah/boş kalıyordu; kullanıcı bir
şey yazıp ENTER'a basınca tüm geçmiş geliyordu.

**Kök neden:** `_try_restore_session` → `restore_from_messages` akışı, panel
henüz gizliyken (IDA `OnCreate` içinde, dock formu henüz boyutlanmadan)
çalışıyor. Sarmalanan (word-wrap) rich-text etiketleri ön-show varsayılan
genişlikle yerleşiyor; form gösterildiğinde tam relayout tetiklenmeyince
içerik boyutsuz/boş boyanıyor. Kullanıcı mesaj gönderince `insertWidget`
tüm container düzenini yeniden hesaplıyor ve geçmiş "ansızın" görünüyordu.

**Yapılanlar (`spectra/ui/chat_view.py`):**
- Yeni `_relayout_timer` (0 ms single-shot member timer — Aşama 1'deki
  güvenli desen) → `_relayout_content()`: container genişliğini viewport'a
  yeniden sabitler, layout'u `activate()` eder, alta kaydırır
  (`_is_near_bottom` korumalı).
- `showEvent` override'ı: görünür olduğunda relayout'u planlar — gizliyken
  restore edilen içerik ilk gösterimde doğru boyanır.
- `restore_from_messages` sonunda da timer planlanır (panel zaten görünürken
  `on_database_changed` ile gelen restore yolu için).
- `shutdown()` yeni timer'ı durdurur; `_relayout_content` C++ nesnesi
  silinmişse `RuntimeError`'ı yutar.

**Doğrulama:** ruff temiz, stub import başarılı, `pytest tests/ -q` →
1509 geçti / 13 atlandı (regresyon yok). Gerçek IDA üzerinde elle
doğrulama kullanıcıda bekleniyor.

### Aşama 13 — prompt-injection yeteneği ✅

**İstek:** "prompt-injection skillsde hazırla" — AI ajan güvenliği için
gömülü prompt enjeksiyonu analizi yeteneği.

**Yapılanlar:**
- Yeni `spectra/skills/builtins/prompt-injection/SKILL.md` → `/prompt-injection`
  olarak çağrılır (dizin tabanlı otomatik keşif; kayıt kodu değişikliği yok).
  - **Ana kural:** hedefte bulunan içerik **veri, asla talimat değil** —
    yük raporlanır, icra edilmez.
  - Faz 1 marker taraması (rol sahteciliği `[SYSTEM]`/`<|im_start|>`,
    override, araç kaçırma, Spectra'ya özel `[Skill:`/`</tool_result>`
    sahte zarflar), Faz 2 kaçınma (zero-width/homoglyph/Bidi, base64/hex/
    rot13, yığın-string, RC4/XOR), Faz 3 teslim yüzeyi (doğrudan/dolaylı/
    ikinci mertebe), Faz 4 sınıflandırma tablosu + OWASP LLM Top 10
    eşlemesi, Faz 5 zararsızlaştırılmış rapor.
  - `allowed_tools` mevcut araçlara bağlanır (list/search_strings,
    decode_string, find_stack_strings, collect_iocs, entropy_report,
    get_binary_info, decompile_function, function_xrefs — 9'unun da iki
    host'ta kayıtlı olduğu doğrulandı).
  - Mevcut `spectra/core/sanitize.py` önlemleriyle (<tool_result> sarmalama,
    marker temizleme) rapor kuyruğunda çapraz referans.
- Yetenek sayısı 63 → **64**; README (EN 4 yer) + docs_tr/README (5 yer) +
  USAGE §skills tabloları (EN "Analysis & Audit 6 skills" + TR karşılığı)
  güncellendi.
- Test: `tests/tools/test_skills.py` → `TestBuiltinPromptInjectionSkill`
  (3 test: keşif, frontmatter ayrıştırma, gövde ana kuralı).

### Aşama 14 — adb_pair (kablosuz eşleşme) + sohbette Ctrl+F arama ✅

**İstek:** (1) "ADB tool için tcp üzerinden connection" — `adb connect` zaten
var'dı; eksik olan ilk eşleşme adımı `adb pair` aracı olarak eklendi.
(2) "konuşmada Ctrl+F yaptığımda istediğim kelimeyi arayabileyim".

**Yapılanlar (`spectra/tools/adb.py`):**
- Yeni `adb_pair(ip_port, code)` — Android 11+ kablosuz hata ayıklama için
  tek seferlik eşleşme. Girdi doğrulaması `_validate_pair_target` (regex:
  adres IPv4/IPv6+port, kod alfanümerik, başta tire yok → adb switch gibi
  yorumlanamaz); başarıda "eşleşme portu ≠ bağlantı portu, şimdi
  adb_connect çağır" yönlendirmesi döner. Kayıt: `register_module(adb)`
  zaten modülün tüm araçlarını alıyor → iki host'ta da otomatik
  (IDA 147 / Binja 149 araç).

**Yapılanlar (`spectra/ui/chat_view.py` + `message_widgets.py` +
`qt_compat.py`):**
- Yüzen arama çubuğu (Ctrl+F → sağ üstte QFrame; ilk açılışta tembel
  kurulur). Enter/▼ sonraki, Shift+Enter/▲ önceki (sarmalı), Esc kapatır,
  sayaç "i/n". Geçerli eşleşme altın çerçeveyle vurgulanır (orijinal
  styleSheet saklanıp geri konur), `ensureWidgetVisible` ile kaydırma.
- Arama metni: kullanıcı/asistan/hata mesajları üzerinden `search_text()`
  (asistanda ham Markdown kaynağı — düşünme bloğu dahil); büyük/küçük
  harf duyarsız, görsel sırayla. `clear_chat` arama durumunu temizler.
- `qt_compat` üç binding bloğuna `QShortcut` + `QKeySequence` eklendi;
  `tests/qt_stubs.py` aynı adlarla genişletildi.

**Testler:** `tests/tools/test_adb.py` +7 (doğrulama, başarı yönlendirmesi,
adb çağrılmama), `tests/tools/test_chat_view.py` +8 (eşleşme toplama,
sarmalı gezinme, sayaç, kapatma — Qt olmadan `__new__` deseniyle).

**Dokümantasyon:** README + docs_tr/README araç sayıları 146/148 → 147/149;
USAGE §4.4 (EN+TR) Ctrl+F bileşen satırı; USAGE §13.4 (EN+TR) kablosuz
bağlantı paragrafı.

---

## Sonraki Aşamalar (öneri sırasıyla)

### Aşama 4 — SSL tespitini saha doğrulaması ve derinleştirme ⬜

- [ ] Gerçek bir pin'li Android NDK kütüphanesinde (BoringSSL
      `SSL_CTX_set_custom_verify`) ve bir iOS uygulamasında
      (SecTrustSetAnchorCertificates) tespiti elle doğrula.
- [ ] Frida script üretimini hook hedeflerinden otomatik besle (şu an
      katalogdan statik metin).
- [ ] JNI `RegisterNatives` çözümlemesiyle dinamik bağlanan trust-manager
      metodlarını da yakala (isim tablosundan kayıt edilmeyenler için).
- [ ] Sertifikaların gömülü DER blob'ları olarak taranması (PEM'in yanı
      sıra `30 82 …` ASN.1 imzası taraması).

### Aşama 5 — Güvenlik geçitlerinin incelikleri ⬜

- [ ] Güvensiz komut modu etkinken UI'da kalıcı bir uyarı bandı göster.
- [ ] İzin durumunu oturum günlüğüne yaz (denetim izi).
- [ ] Araç başına kapsam (örn. yalnızca adb_shell) — config şeması
      genişletmesi gerektirir; şimdilik bilinçli olarak tek anahtar.

### Aşama 6 — Update akışı sağlamlığı ⬜

- [ ] İndirme sırasında iptal düğmesi (sinyal tabanlı akış artık buna izin
      veriyor).
- [ ] content-length eksikse tahmini ilerleme (indirilen byte / son
      bilinen boyut eğrisi).
- [ ] Kurulum sonrası otomatik yeniden başlatma seçeneği.

---

## Bakım Notları

- Test paketinde `sys.modules` mock kirliliği iki belgeli tuzak üretir:
  (1) IDA mock'ları en son kurulan kazanır → test edilen modülü
  `setUpModule`'da `importlib.reload` et, (2) `spectra.core.config`
  stub'lanır → gerçek kaydet/yükle iddiaları alt süreçte çalıştırılmalı.
  Ayrıntı: `docs/DEVELOPMENT.md` → "Test-suite gotchas".
- Sürüm artırırken tek kaynak `update.json`; `ci-local.sh` sürüm
  tutarlılığını denetler.

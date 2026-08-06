# Spectra Aracı Ekleme Kılavuzu

Spectra'ya yeni aracı eklemanın 3 ana yolu vardır:

## 1. Yeni Bir Skill Oluşturma (En Kolay)

Skill'ler aslında aracı gibi davranır. Yeni bir skill oluşturarak yeni bir aracı ekleyebilirsiniz.

### Skill Yapısı:

```
my-custom-agent/
├── skill.md           # Aracı tanımı ve talimatlar
└── (isteğe bağlı)     # Ek dosyalar (varsa)
```

### Örnek: Yeni Bir Aracı Oluşturma

```bash
# 1. Yeni skill dizini oluştur
cd /path/to/Spectra/spectra/skills/builtins
mkdir my-custom-agent
cd my-custom-agent

# 2. skill.md oluştur
cat > skill.md << 'EOF'
---
name: My Custom Agent
description: Custom analysis agent - specialized in a specific field
tags: [custom, analysis, specialized]
mode: plan
---
Task: This agent performs X analysis.

## Approach
- Step 1: ...
- Step 2: ...
- Step 3: ...

## Tools Used
- tool_name_1
- tool_name_2

## Workflow
1. tool_name_1 → ...
2. tool_name_2 → ...
3. ...

## Expected Output
- ...
EOF
```

### 3. Skill'i Kaydet

```bash
# Skill otomatik yüklenir
# Spectr bir sonraki başlatışta skill'i keşfeder
```

### 4. IDA Pro'da Kullanım

```
// Spectra panelinde (Ctrl+Shift+I)
/my-custom-analyze

// Veya otomatik olarak
/my-custom-analyze this function
```

## 2. Mevcut Bir Skill'i Kopyalama ve Değiştirme

Mevcut bir skill'i kopyalayın ve ihtiyaçlarınıza göre değiştirin.

### Örnek: Vuln-Audit Skill'ini Özelleştirme

```bash
# 1. vuln-audit skill'ini kopyala
cd /path/to/Spectra/spectra/skills/builtins
cp -r vuln-audit my-vuln-audit
cd my-vuln-audit

# 2. skill.md dosyasını düzenle
nano skill.md

# 3. Yeni isim ve açıklama
---
name: My Vulnerability Audit
description: Custom vulnerability scan
tags: [security, vuln-audit, custom]
mode: plan
---
Task: This custom vulnerability audit agent does:
- Search for stack overflow
- Search for heap overflow
- SQL injection scan
- XSS scan

## Approach
...
```

### 4. Skill'i Kaydet

Skill otomatik yüklenir, özel kayıt gerekmez.

## 3. A2A (Agent-to-Agent) Aracı Ekleme

Spectra dışındaki aracıları Spectra ile entegre edin.

### Yapılandırma Dosyası:

```json
// ~/.idapro/spectra/config.json
{
  "a2a_agents": [
    {
      "name": "Ghidra Agent",
      "type": "external",
      "endpoint": "http://localhost:8080/agent",
      "api_key": "ghidra-api-key",
      "capabilities": ["decompile", "analyze", "disassemble"]
    },
    {
      "name": "Binary Ninja Cloud Agent",
      "type": "external",
      "endpoint": "https://api.binary.ninja.com/v1/agent",
      "api_key": "bn-api-key",
      "capabilities": ["lift", "analyze", "decompile"]
    }
  ]
}
```

### Kullanım:

```
// Spectra panelinde
/ask Ghidra Agent: Decompile this function at 0x401000

// Otomatik yönlendirme
Spectra görevi dış aracıya yönlendirir
```

## 4. Özel Aracı İşleyicisi Yazma (Gelişmiş)

Python kodu ile özel aracı işleyicileri yazabilirsiniz.

### Aracı İşleyicisi Örneği:

```python
# /path/to/Spectra/spectra/agents/custom_agent.py

from typing import Any, Dict
from ..agent.base import AgentHandler

class CustomAnalyzerAgent(AgentHandler):
    """Custom analysis agent handler."""

    def __init__(self):
        super().__init__()
        self.name = "Custom Analyzer"
        self.version = "1.0.0"

    def can_handle(self, task: str) -> bool:
        """Can this agent handle the task?"""
        keywords = ["analyze", "scan", "examine"]
        return any(keyword in task.lower() for keyword in keywords)

    def execute(self, task: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the task."""

        # 1. Görevi analiz et
        analysis_result = self._analyze_task(task)

        # 2. IDA API'sini kullan
        results = []
        for address in analysis_result["addresses"]:
            result = self._analyze_address(address)
            results.append(result)

        # 3. Sonuçları döndür
        return {
            "agent": self.name,
            "task": task,
            "results": results,
            "status": "completed"
        }

    def _analyze_task(self, task: str) -> Dict[str, Any]:
        """Analyze the task."""
        # Görevden adresleri çıkar
        import re
        addresses = re.findall(r'0x[0-9a-fA-F]+', task)
        return {"addresses": addresses}

    def _analyze_address(self, address: int) -> Dict[str, Any]:
        """Analyze address."""
        # IDA API'sini kullan
        try:
            import idaapi
            func_name = idaapi.get_func_name(address)
            return {
                "address": address,
                "function": func_name,
                "analysis": "manual review needed"
            }
        except:
            return {
                "address": address,
                "error": "Failed to analyze"
            }
```

### Aracıyı Kaydetme:

```python
# /path/to/Spectra/spectra/agents/__init__.py

from .custom_agent import CustomAnalyzerAgent

# Aracı kaydet
AGENT_REGISTRY.register(CustomAnalyzerAgent)
```

## 5. Alt Aracılar Tanımlama (Keşif Modu İçin)

Keşif modunda kullanılan alt aracıları tanımlayabilirsiniz.

```python
# /path/to/Spectra/spectra/agents/subagents.py

from typing import Any, Dict

class FunctionAnalyzerSubagent:
    """Function analysis subagent."""

    def analyze_functions(self, addresses: list[int]) -> Dict[str, Any]:
        """Analyze functions."""
        results = {}

        for addr in addresses:
            try:
                # Analiz için IDA API'sini kullan
                import idaapi
                func = idaapi.get_func(addr)
                results[addr] = {
                    "name": func.get_name(),
                    "size": func.get_size(),
                    "bounds": func.get_bounds()
                }
            except:
                results[addr] = {"error": "Failed to analyze"}

        return results
```

## 6. En Pratik: Hızlı Aracı Oluşturma

### Şablon Skill Dosyası:

```markdown
---
name: Quick Analysis Agent
description: Automatic and fast binary analysis
tags: [fast, analysis, automated]
mode: auto
---
Task: This agent analyzes binary quickly.

## Auto-Analysis Workflow
1. `get_binary_info` → get general info
2. `list_imports` → scan imports
3. `list_exports` → scan exports
4. `search_functions` → find critical functions
5. Create auto-report

## Speed Optimization
- Do parallel analysis
- Focus only on critical areas
- Don't follow deep recursion

## Quick Report
- Summary analysis result
- Risk scores
- Recommended next steps
```

## 7. Aracı Test Etme

### Test Komutu:

```bash
# Aracı test et
cd /path/to/Spectra
python -m pytest tests/agent/test_agent.py -v

# Belirli skill'i test et
python -m pytest tests/tools/test_skills.py::test_my_custom_agent -v
```

### IDA Pro'da Test:

```
// Spectra panelinde
/test-agent my-custom-agent "Analyze 0x401000"
```

## 8. Aracı Yönetimi

### Aktif Aracıları Görüntüle:

```
// Spectra panelinde
/agents list

// Çıktı:
Active Agents: 3
- Main Orchestrator
- Function Analyzer (0x401000)
- String Searcher
```

### Aracıları Kontrol Et:

```
/agents pause          // Tüm aracıları durdur
/agents resume         // Aracıları devam ettir
/agents stop           // Tüm aracıları durdur
```

## 9. Aracı Yapılandırması

### Aracı Davranışını Ayarla:

```json
// ~/.idapro/spectra/config.json
{
  "exploration_turn_limit": 100,    // Kaç tur sonra durdurulacak
  "max_concurrent_agents": 5,      // Maksimum paralel aracı sayısı
  "agent_timeout": 300,          // Aracı zaman aşımı (saniye)
  "subagent_auto_cleanup": true  // Tamamlanan aracıları otomatik temizle
}
```

## 10. Örnek: Kriptografik Analiz Aracı

### Kripto Analiz Skill'i:

```markdown
---
name: Crypto Analyst
description: Cryptographic primitive and algorithm analysis
tags: [crypto, encryption, analysis]
mode: plan
---
Task: This agent analyzes cryptographic usage in binary.

## Crypto Patterns
- Block cipher usage (AES, DES)
- Stream cipher usage (RC4, ChaCha20)
- Hash function usage (SHA-1, SHA-256, MD5)
- Public key cryptography (RSA, ECC)
- Random number generation

## Detection Methods
1. API detection: CryptEncrypt, CryptDecrypt, etc.
2. Constant key detection
3. Mode and padding detection
4. Key length analysis

## Analysis Workflow
1. `search_functions` → find crypto functions
2. `decompile_function` → analyze each function
3. Constant scan → search for keys and IVs
4. Cross-reference → find crypto usage areas
```

### Kullanım:

```
// IDA Pro'da
/crypto Analyze encryption usage in this binary

// Otomatik
/crypto Find all AES-256 implementations
```

## Özet: Hangi Yöntem Ne Zaman Kullanılmalı?

| Yöntem | Zorluk | Esneklik | Kullanım Durumu |
|--------|------------|-------------|----------|
| **Skill Oluşturma** | Kolay | Yüksek | Özel analiz ihtiyaçları |
| **Skill Kopyalama** | Çok Kolay | Orta | Mevcut aracıyı özelleştirme |
| **A2A Aracı** | Orta | Düşük | Dış araç entegrasyonu |
| **Özel İşleyici** | Zor | Çok Yüksek | Tam kontrol, gelişmiş |

**Başlangıç için öneri:** Önce mevcut bir skill'i kopyalayıp değiştirin, sonra kendi skill'inizi oluşturun.

**Dokümantasyon:**
- Skill yazma: `/path/to/Spectra/spectra/skills/builtins/` içindeki skill.md dosyalarına bakın
- Aracı API: `/path/to/Spectra/spectra/agent/` içindeki modülleri inceleyin
- Test örnekleri: `/path/to/Spectra/tests/agent/` içindeki test dosyalarına bakın

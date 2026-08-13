---
name: Cryptography Analysis
description: Cryptography analysis — algorithm identification, mathematical operations, constant detection, and security evaluation
tags: [cryptography, crypto, security, algorithms]
---

Task: Cryptography Analysis. You are analyzing cryptographic implementations, identifying algorithms, and evaluating security.

## Approach

Focus on identifying cryptographic primitives through constants, mathematical operations, and code patterns. Cryptographic code is distinctive — S-boxes, round constants, bit operations, and modular arithmetic are reliable indicators.

## When to Use

Use this skill when:
- Identifying cryptographic algorithms and primitives in binary code
- Analyzing mathematical operations and constants
- Evaluating cryptographic security and implementation quality
- Reverse engineering custom crypto implementations
- Detecting side-channel vulnerabilities
- Analyzing key management and derivation functions
- Understanding cryptographic protocols and constructions
- Assessing random number generation and entropy sources

## Workflow

1. **Constant Detection**
   - Search for cryptographic constants: S-boxes, round constants, primes
   - Look for magic bytes and initialization vectors
   - Identify standard algorithm constants (AES, DES, RSA, ECC)

2. **Pattern Recognition**
   - Identify bitwise operations (XOR, rotation, bit shifting, masking)
   - Recognize modular arithmetic and finite field operations
   - Find lookup tables and S-box substitutions
   - Detect mode of operation patterns (ECB, CBC, GCM, CTR)

3. **Algorithm Identification**
   - Match known cryptographic code patterns
   - Identify S-boxes, lookup tables, and round functions
   - Recognize key schedules and expansion routines
   - Determine symmetric vs asymmetric cryptography

4. **Security Evaluation**
   - Test for timing side-channels
   - Evaluate constant-time properties
   - Assess key management practices
   - Check for common implementation vulnerabilities
   - Analyze random number generation quality

## Algorithm Identification

**Symmetric Ciphers:**
- AES: SubBytes, ShiftRows, MixColumns, AddRoundKey
- DES: Feistel network, S-boxes, permutations
- ChaCha20: Quarter round function, 20 rounds

**Hash Functions:**
- SHA-256: 8 initialization vectors, 64 round constants
- MD5: 4 rounds, 64 operations per round
- BLAKE2: BLAKE2b or BLAKE2s parameters

**Asymmetric:**
- RSA: Modular exponentiation, prime generation, padding (PKCS#1, OAEP)
- ECC: Point addition, scalar multiplication, field operations
- DH/ECDH: Key exchange protocols, prime field operations

## Mathematical Analysis

**Bitwise Operations:**
- XOR: Combining data, simple encryption
- Rotation: Byte rotation in AES, bit rotation in SHA
- Bit shifting: Multiplication/division by powers of 2
- Masking: Extracting or setting specific bits

**Modular Arithmetic:**
- Modular exponentiation: RSA encryption/decryption
- Finite field operations: AES MixColumns in GF(2^8)
- Prime field operations: ECC point operations
- Polynomial arithmetic: CRC, hash functions

## Security Issues to Identify

**Side Channels:**
- Timing variations in secret-dependent branches
- Cache behavior leaks via table lookups
- Power analysis vulnerabilities
- Constant-time violations

**Implementation Flaws:**
- Weak key generation or derivation
- Incorrect padding or padding oracle vulnerabilities
- Reused nonces or initialization vectors
- Missing authentication (MAC-then-encrypt vs encrypt-then-MAC)
- Predictable random number generation

**Protocol Issues:**
- Downgrade attacks
- Lack of forward secrecy
- Weak cipher suite selection
- Insecure key exchange

## Output

Detailed cryptographic analysis including:
- Identified algorithms and cryptographic primitives
- Mathematical operation explanations and purposes
- Constant detection and algorithm confirmation
- Security vulnerabilities and weaknesses
- Side-channel analysis and timing issues
- Implementation quality assessment
- Recommendations for improvements

Focus on mathematical precision and concrete algorithm identification with code examples and security findings.

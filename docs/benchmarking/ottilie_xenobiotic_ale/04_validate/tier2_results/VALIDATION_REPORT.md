# Ottilie Benchmark Validation Report

**Generated**: 2026-05-29 10:18
**Pipeline output**: `output_ottilie_tier2`

## 1. SNV/INDEL Concordance (HaplotypeCaller vs Sup Data 4)

**Overall sensitivity**: 339/343 (98.8%)

### Undetected variants (4)

| Sample | Position | Ref>Alt | Type | Gene | Effect | Flags |
|--------|----------|---------|------|------|--------|-------|
| Stauro--2Res2a | I:59020 | G>A | SNP | PTA1 | missense_variant |  |
| MMV1078458--4R3a | VIII:485367 | T>A | SNP | ERG9 | missense_variant |  |
| Meb--1Res2a | III:316617 | T>G | SNP | intergenic | intergenic_region |  |
| GNFpf2740--15_R5a | XII:1071524 | TAGGGCTATGTAGAAGTGCTGTAGGGCTAAAGAACAGGGTTTCA>T | INDEL | intergenic | intergenic_region |  |


## 2. CNV Concordance (CNVKit vs Sup Data 5)

**Detection rate**: 18/24 (75.0%)

| Event type | Detected | Total | Rate |
|------------|----------|-------|------|
| Whole chromosome duplication | 9 | 11 | 82% |
| Focal amplification | 9 | 13 | 69% |

### Undetected events (6)

| Sample | Chr | Event type | Chr affected | CNVKit segments |
|--------|-----|------------|--------------|-----------------|
| Doxorubicin-135-R2b | XIII | focal amp | 0% | no gain; all segments: XIII:0-204873 (205kb) cn=2 log2=0.096; XIII:204873-924431 (720kb) cn=2 log2=-0.007 |
| Etoposide-R7b-2 | XII | whole chr dup | 58% | XII:449240-1078177 (629kb) cn=3 log2=0.503 |
| Etoposide-R9b-2 | XII | whole chr dup | 58% | XII:449240-1078177 (629kb) cn=3 log2=0.374 |
| MMV085203-11R3a | XIV | focal amp | 0% | no gain; all segments: XIV:0-784333 (784kb) cn=2 log2=0.022 |
| MMV085203-7R3a | XIV | focal amp | 0% | no gain; all segments: XIV:0-784333 (784kb) cn=2 log2=0.004 |
| Tavabarole-9Res2c | XIII | focal amp | 0% | no gain; all segments: XIII:0-204873 (205kb) cn=2 log2=0.083; XIII:204873-924431 (720kb) cn=2 log2=-0.008 |


## 3. Detected Events

### SNV/INDEL per-sample concordance (85 samples)

| Sample | Truth | Pipeline | Evolved-unique | TP | FN | Sensitivity | Precision |
|--------|-------|----------|----------------|----|----|-------------|-----------|
| Etoposide-R9b-2 | 3 | 277 | 46 | 3 | 0 | 100.0% | 6.5% |
| Etoposide-R7b-2 | 4 | 297 | 59 | 4 | 0 | 100.0% | 6.8% |
| Etoposide-R4b-2 | 3 | 280 | 46 | 3 | 0 | 100.0% | 6.5% |
| Etoposide--R10b-2 | 6 | 287 | 60 | 6 | 0 | 100.0% | 10.0% |
| Doxorubicin-135-R2b | 4 | 287 | 54 | 4 | 0 | 100.0% | 7.4% |
| Doxorubicin-24R3a | 1 | 297 | 63 | 1 | 0 | 100.0% | 1.6% |
| Diethylstilbestrol--17C | 1 | 299 | 66 | 1 | 0 | 100.0% | 1.5% |
| Diethylstilbestrol--15A | 2 | 289 | 60 | 2 | 0 | 100.0% | 3.3% |
| Diethylstilbestrol--14C | 3 | 262 | 48 | 3 | 0 | 100.0% | 6.2% |
| Diethylstilbestrol--13C | 2 | 296 | 53 | 2 | 0 | 100.0% | 3.8% |
| Wortmannin-17-R3a | 1 | 291 | 62 | 1 | 0 | 100.0% | 1.6% |
| Wortmannin-13R3a | 5 | 302 | 72 | 5 | 0 | 100.0% | 6.9% |
| TCMDC124263--11-R3a | 5 | 311 | 75 | 5 | 0 | 100.0% | 6.7% |
| TCMDC124263--3-R3a | 5 | 271 | 47 | 5 | 0 | 100.0% | 10.6% |
| Tavabarole-9Res2c | 1 | 296 | 59 | 1 | 0 | 100.0% | 1.7% |
| Tav--8Res2b | 1 | 304 | 62 | 1 | 0 | 100.0% | 1.6% |
| Stauro--3Res2a | 4 | 300 | 70 | 4 | 0 | 100.0% | 5.7% |
| Stauro--2Res2a | 6 | 310 | 74 | 5 | 1 | 83.3% | 6.8% |
| DDD01027481--9_R3a | 4 | 281 | 59 | 4 | 0 | 100.0% | 6.8% |
| CBR868-5--R2a | 5 | 304 | 69 | 5 | 0 | 100.0% | 7.2% |
| CBR868-4--R2a | 1 | 310 | 61 | 1 | 0 | 100.0% | 1.6% |
| CBR868-2--R2a | 2 | 301 | 66 | 2 | 0 | 100.0% | 3.0% |
| CBR868--15R3a | 3 | 293 | 69 | 3 | 0 | 100.0% | 4.3% |
| DDD01027481--8_R3a | 4 | 315 | 98 | 4 | 0 | 100.0% | 4.1% |
| CBR110-15R3a | 4 | 281 | 55 | 4 | 0 | 100.0% | 7.3% |
| CBR110-14R3a | 7 | 281 | 53 | 7 | 0 | 100.0% | 13.2% |
| CBR668--7-R3b | 3 | 257 | 46 | 3 | 0 | 100.0% | 6.5% |
| CBR668--5-R3b | 7 | 257 | 54 | 7 | 0 | 100.0% | 13.0% |
| DDD01027481--11_R3a | 2 | 302 | 81 | 2 | 0 | 100.0% | 2.5% |
| CBR668--4-R3a | 6 | 258 | 55 | 6 | 0 | 100.0% | 10.9% |
| CBR668--3-R3a | 5 | 272 | 56 | 5 | 0 | 100.0% | 8.9% |
| CBR668--2-R3b | 7 | 279 | 64 | 7 | 0 | 100.0% | 10.9% |
| CBR668--1-R3b | 2 | 237 | 40 | 2 | 0 | 100.0% | 5.0% |
| CBR113-7R4a | 8 | 327 | 95 | 8 | 0 | 100.0% | 8.4% |
| CBR113--1-R4a | 4 | 293 | 63 | 4 | 0 | 100.0% | 6.3% |
| CHX--Cy73-2 | 7 | 283 | 32 | 7 | 0 | 100.0% | 21.9% |
| MMV665909--8R4a | 7 | 291 | 55 | 7 | 0 | 100.0% | 12.7% |
| MMV665882--16_R4a | 15 | 327 | 108 | 15 | 0 | 100.0% | 13.0% |
| MMV665852--17R3a | 1 | 280 | 60 | 1 | 0 | 100.0% | 1.7% |
| MMV665852--15R3a | 4 | 269 | 48 | 4 | 0 | 100.0% | 8.3% |
| MMV665852--13R3b | 4 | 269 | 54 | 4 | 0 | 100.0% | 9.3% |
| MMV665852--R1a-2 | 2 | 278 | 43 | 2 | 0 | 100.0% | 4.7% |
| MMV665852--R39b | 3 | 271 | 48 | 3 | 0 | 100.0% | 6.2% |
| MMV665807--R5-2 | 4 | 278 | 22 | 4 | 0 | 100.0% | 18.2% |
| MMV665807--R4-2 | 2 | 277 | 33 | 2 | 0 | 100.0% | 6.1% |
| MMV665794-8R9c | 7 | 282 | 58 | 7 | 0 | 100.0% | 12.1% |
| MMV665794-7R9c | 10 | 278 | 50 | 10 | 0 | 100.0% | 20.0% |
| MMV665794-11R9c | 3 | 290 | 58 | 3 | 0 | 100.0% | 5.2% |
| MMV665794-10R9c | 11 | 282 | 65 | 11 | 0 | 100.0% | 16.9% |
| MMV396736--R10-2 | 1 | 265 | 35 | 1 | 0 | 100.0% | 2.9% |
| MMV306025--R1-2 | 9 | 294 | 45 | 9 | 0 | 100.0% | 20.0% |
| MMV1469689--5-R2a | 4 | 298 | 44 | 4 | 0 | 100.0% | 9.1% |
| MMV1469689--1-R2a | 5 | 310 | 74 | 5 | 0 | 100.0% | 6.8% |
| Z46108311--2R2c | 2 | 274 | 53 | 2 | 0 | 100.0% | 3.8% |
| MMV1078458--9_R3a | 6 | 318 | 92 | 6 | 0 | 100.0% | 6.5% |
| MMV1078458--8_R4a | 5 | 326 | 104 | 5 | 0 | 100.0% | 4.8% |
| MMV1078458--7_R3a | 2 | 331 | 113 | 2 | 0 | 100.0% | 1.8% |
| MMV1078458--6R3a | 3 | 295 | 63 | 3 | 0 | 100.0% | 4.8% |
| MMV1078458--5R3a | 1 | 298 | 62 | 1 | 0 | 100.0% | 1.6% |
| MMV1078458--4R3a | 2 | 294 | 66 | 1 | 1 | 50.0% | 1.5% |
| MMV1078458--2R3a | 1 | 291 | 72 | 1 | 0 | 100.0% | 1.4% |
| MMV1078458--10_R3a | 4 | 312 | 85 | 4 | 0 | 100.0% | 4.7% |
| MMV1007245--13_R4b | 1 | 345 | 118 | 1 | 0 | 100.0% | 0.8% |
| MMV085203-7R3a | 2 | 272 | 50 | 2 | 0 | 100.0% | 4.0% |
| MMV085203-11R3a | 2 | 273 | 59 | 2 | 0 | 100.0% | 3.4% |
| MMV019017--R7-2 | 1 | 265 | 45 | 1 | 0 | 100.0% | 2.2% |
| BMS983970-2R1e | 1 | 308 | 67 | 1 | 0 | 100.0% | 1.5% |
| MMV000570--R4-2 | 3 | 268 | 29 | 3 | 0 | 100.0% | 10.3% |
| MMV000570--R3-2 | 1 | 273 | 27 | 1 | 0 | 100.0% | 3.7% |
| Meb--1Res2a | 10 | 312 | 72 | 9 | 1 | 90.0% | 12.5% |
| Lomerizine--21R3b | 2 | 288 | 57 | 2 | 0 | 100.0% | 3.5% |
| Lapatanib--6R6b | 7 | 270 | 51 | 7 | 0 | 100.0% | 13.7% |
| ART--R5-2 | 2 | 287 | 60 | 2 | 0 | 100.0% | 3.3% |
| PMA1--D1 | 5 | 319 | 89 | 5 | 0 | 100.0% | 5.6% |
| NITD609--R17 | 1 | 265 | 23 | 1 | 0 | 100.0% | 4.3% |
| NITD609--661-2 | 3 | 270 | 44 | 3 | 0 | 100.0% | 6.8% |
| NITD609--652-2 | 4 | 279 | 43 | 4 | 0 | 100.0% | 9.3% |
| HygromycinB-36R8a | 10 | 278 | 61 | 10 | 0 | 100.0% | 16.4% |
| Hecto--7Res2a | 3 | 313 | 76 | 3 | 0 | 100.0% | 3.9% |
| Hecto--16Res2a | 3 | 289 | 59 | 3 | 0 | 100.0% | 5.1% |
| DS4-R6-2 | 1 | 301 | 66 | 1 | 0 | 100.0% | 1.5% |
| DS29--R6-2 | 6 | 296 | 50 | 6 | 0 | 100.0% | 12.0% |
| DS28-R5-2 | 2 | 292 | 47 | 2 | 0 | 100.0% | 4.3% |
| GNFpf2740--15_R5a | 10 | 292 | 70 | 9 | 1 | 90.0% | 12.9% |
| GNF-Pf-1618-7R2b | 7 | 283 | 65 | 7 | 0 | 100.0% | 10.8% |

### CNV per-event concordance (24 events)

| Sample | Chromosome | Truth event | Detected | CN | log2 | Chr affected |
|--------|------------|-------------|----------|------|------|--------------|
| BMS983970-2R1e | X | Whole chromosome duplication | YES | 3 | 0.613 | 100% |
| CBR110-15R3a | I | Whole Chromosome Duplication | YES | 3 | 0.329 | 100% |
| CBR113-7R4a | XV | Amplification | YES | 4 | 0.762 | 10% |
| DS28-R5-2 | II | Whole chromosome duplication | YES | 4 | 0.934 | 100% |
| DS4-R6-2 | XIII | Whole chromosome duplication | YES | 4 | 0.970 | 100% |
| Diethylstilbestrol--15A | IV | Amplification | YES | 4 | 0.842 | 8% |
| Doxorubicin-135-R2b | XIII | Amplification | NO |  |  | 0% |
| Doxorubicin-24R3a | IX | Whole chromosome duplication | YES | 4 | 0.929 | 100% |
| Etoposide-R4b-2 | V | Whole chromosome duplication | YES | 3 | 0.270 | 100% |
| Etoposide-R7b-2 | XII | Whole chromosome duplication | NO |  |  | 58% |
| Etoposide-R9b-2 | XII | Whole chromosome duplication | NO |  |  | 58% |
| GNF-Pf-1618-7R2b | XVI | Amplification | YES | 6 | 1.513 | 11% |
| GNFpf2740--15_R5a | XVI | Amplification | YES | 5 | 1.212 | 2% |
| HygromycinB-36R8a | XI | Whole chromosome duplication | YES | 4 | 0.958 | 100% |
| MMV085203-11R3a | XIV | Amplification | NO |  |  | 0% |
| MMV085203-7R3a | XIV | Amplification | NO |  |  | 0% |
| MMV665794-10R9c | XVI | Amplification | YES | 12 | 2.515 | 3% |
| MMV665794-11R9c | XVI | Amplification | YES | 13 | 2.588 | 2% |
| MMV665794-7R9c | XVI | Amplification | YES | 17 | 3.075 | 3% |
| MMV665794-8R9c | XVI | Amplification | YES | 14 | 2.725 | 2% |
| Tavabarole-9Res2c | XIII | Amplification | NO |  |  | 0% |
| Wortmannin-13R3a | XV | Amplification | YES | 5 | 1.118 | 8% |
| Wortmannin-17-R3a | II | Whole Chromosome Duplication | YES | 3 | 0.504 | 100% |
| Wortmannin-17-R3a | VII | Whole Chromosome Duplication | YES | 3 | 0.561 | 100% |

## 4. SV Characterization (Manta + TIDDIT)

| Sample | Parent | Manta | TIDDIT | Union | Consensus | Both | Evolved-unique |
|--------|--------|-------|--------|-------|-----------|------|----------------|
| ART--R5-2 |  | 7(7P) | 53(10P) | 42 | 5 | 5 | 8 |
| BMS983970-2R1e |  | 14(11P) | 140(9P) | 116 | 10 | 10 | 61 |
| CBR110-14R3a |  | 15(6P) | 110(12P) | 94 | 10 | 10 | 41 |
| CBR110-15R3a |  | 22(15P) | 170(30P) | 136 | 17 | 17 | 80 |
| CBR113--1-R4a |  | 40(30P) | 120(8P) | 118 | 23 | 23 | 66 |
| CBR113-7R4a |  | 27(19P) | 159(9P) | 144 | 17 | 17 | 81 |
| CBR668--1-R3b |  | 15(12P) | 32(6P) | 37 | 8 | 8 | 16 |
| CBR668--2-R3b |  | 15(9P) | 78(8P) | 75 | 9 | 9 | 22 |
| CBR668--3-R3a |  | 20(16P) | 54(6P) | 58 | 11 | 11 | 20 |
| CBR668--4-R3a |  | 15(10P) | 48(5P) | 47 | 11 | 11 | 14 |
| CBR668--5-R3b |  | 19(13P) | 56(9P) | 63 | 9 | 9 | 33 |
| CBR668--7-R3b |  | 16(11P) | 50(9P) | 52 | 10 | 10 | 20 |
| CBR868--15R3a |  | 28(22P) | 62(8P) | 72 | 15 | 15 | 28 |
| CBR868-2--R2a |  | 13(9P) | 97(12P) | 90 | 10 | 10 | 47 |
| CBR868-4--R2a |  | 24(22P) | 140(11P) | 118 | 14 | 14 | 65 |
| CBR868-5--R2a |  | 25(23P) | 148(11P) | 132 | 15 | 15 | 81 |
| CHX--Cy73-2 |  | 14(12P) | 196(79P) | 186 | 5 | 5 | 90 |
| DDD01027481--11_R3a |  | 26(22P) | 317(10P) | 305 | 18 | 18 | 257 |
| DDD01027481--8_R3a |  | 17(14P) | 287(24P) | 265 | 13 | 13 | 209 |
| DDD01027481--9_R3a |  | 16(9P) | 258(11P) | 242 | 10 | 10 | 188 |
| DS28-R5-2 |  | 8(7P) | 93(8P) | 70 | 5 | 5 | 26 |
| DS29--R6-2 |  | 8(7P) | 50(7P) | 44 | 5 | 5 | 9 |
| DS4-R6-2 |  | 15(10P) | 69(7P) | 65 | 7 | 7 | 17 |
| Diethylstilbestrol--13C |  | 13(9P) | 75(7P) | 73 | 10 | 10 | 28 |
| Diethylstilbestrol--14C |  | 14(10P) | 54(7P) | 56 | 8 | 8 | 18 |
| Diethylstilbestrol--15A |  | 10(6P) | 59(7P) | 58 | 7 | 7 | 16 |
| Diethylstilbestrol--17C |  | 13(6P) | 71(9P) | 69 | 8 | 8 | 28 |
| Doxorubicin-135-R2b |  | 21(14P) | 89(9P) | 89 | 12 | 12 | 40 |
| Doxorubicin-24R3a |  | 16(6P) | 149(16P) | 118 | 11 | 11 | 68 |
| Etoposide--R10b-2 |  | 10(10P) | 65(9P) | 53 | 5 | 5 | 14 |
| Etoposide-R4b-2 |  | 18(12P) | 83(8P) | 75 | 9 | 9 | 26 |
| Etoposide-R7b-2 |  | 9(9P) | 45(7P) | 44 | 5 | 5 | 6 |
| Etoposide-R9b-2 |  | 19(13P) | 127(11P) | 100 | 15 | 15 | 45 |
| GNF-Pf-1618-7R2b |  | 9(7P) | 56(6P) | 53 | 5 | 5 | 20 |
| GNFpf2740--15_R5a |  | 23(19P) | 286(8P) | 282 | 13 | 13 | 230 |
| Hecto--16Res2a |  | 26(19P) | 210(13P) | 154 | 17 | 17 | 99 |
| Hecto--7Res2a |  | 23(18P) | 179(21P) | 150 | 16 | 16 | 92 |
| HygromycinB-36R8a |  | 15(13P) | 47(8P) | 47 | 8 | 8 | 12 |
| Lapatanib--6R6b |  | 12(7P) | 51(6P) | 54 | 7 | 7 | 15 |
| Lomerizine--21R3b |  | 25(22P) | 52(6P) | 60 | 14 | 14 | 24 |
| MMV000570--R3-2 |  | 8(8P) | 201(51P) | 172 | 5 | 5 | 66 |
| MMV000570--R4-2 |  | 8(8P) | 185(46P) | 158 | 5 | 5 | 61 |
| MMV019017--R7-2 |  | 12(10P) | 74(7P) | 71 | 7 | 7 | 24 |
| MMV085203-11R3a |  | 23(15P) | 56(6P) | 59 | 10 | 10 | 20 |
| MMV085203-7R3a |  | 16(13P) | 53(10P) | 53 | 11 | 11 | 14 |
| MMV1007245--13_R4b |  | 18(14P) | 334(12P) | 330 | 13 | 13 | 270 |
| MMV1078458--10_R3a |  | 15(14P) | 366(10P) | 344 | 12 | 12 | 290 |
| MMV1078458--2R3a |  | 20(14P) | 81(7P) | 74 | 14 | 14 | 30 |
| MMV1078458--4R3a |  | 10(7P) | 130(14P) | 111 | 7 | 7 | 63 |
| MMV1078458--5R3a |  | 16(10P) | 78(8P) | 76 | 6 | 6 | 33 |
| MMV1078458--6R3a |  | 13(10P) | 86(8P) | 79 | 7 | 7 | 34 |
| MMV1078458--7_R3a |  | 19(11P) | 339(15P) | 331 | 14 | 14 | 278 |
| MMV1078458--8_R4a |  | 24(14P) | 371(20P) | 360 | 17 | 17 | 304 |
| MMV1078458--9_R3a |  | 25(12P) | 401(15P) | 392 | 19 | 19 | 333 |
| MMV1469689--1-R2a |  | 24(10P) | 142(10P) | 140 | 18 | 18 | 80 |
| MMV1469689--5-R2a |  | 22(12P) | 128(7P) | 123 | 14 | 14 | 61 |
| MMV306025--R1-2 |  | 15(12P) | 97(9P) | 86 | 10 | 10 | 36 |
| MMV396736--R10-2 |  | 10(8P) | 65(6P) | 55 | 5 | 5 | 19 |
| MMV665794-10R9c |  | 16(16P) | 44(8P) | 45 | 9 | 9 | 17 |
| MMV665794-11R9c |  | 12(10P) | 59(10P) | 57 | 8 | 8 | 16 |
| MMV665794-7R9c |  | 22(19P) | 66(8P) | 74 | 8 | 8 | 28 |
| MMV665794-8R9c |  | 24(18P) | 62(6P) | 62 | 18 | 18 | 22 |
| MMV665807--R4-2 |  | 33(31P) | 195(64P) | 185 | 16 | 16 | 66 |
| MMV665807--R5-2 |  | 11(11P) | 188(73P) | 159 | 5 | 5 | 54 |
| MMV665852--13R3b |  | 13(11P) | 54(7P) | 54 | 8 | 8 | 21 |
| MMV665852--15R3a |  | 14(11P) | 73(8P) | 73 | 7 | 7 | 31 |
| MMV665852--17R3a |  | 15(12P) | 65(6P) | 68 | 9 | 9 | 22 |
| MMV665852--R1a-2 |  | 14(14P) | 169(66P) | 156 | 5 | 5 | 57 |
| MMV665852--R39b |  | 17(14P) | 72(7P) | 70 | 9 | 9 | 35 |
| MMV665882--16_R4a |  | 15(11P) | 324(10P) | 316 | 9 | 9 | 263 |
| MMV665909--8R4a |  | 10(9P) | 58(8P) | 54 | 7 | 7 | 16 |
| Meb--1Res2a |  | 32(20P) | 201(26P) | 174 | 21 | 21 | 118 |
| NITD609--652-2 |  | 8(7P) | 40(9P) | 29 | 7 | 7 | 8 |
| NITD609--661-2 |  | 7(7P) | 154(45P) | 125 | 6 | 6 | 27 |
| NITD609--R17 |  | 14(14P) | 143(48P) | 134 | 7 | 7 | 42 |
| NODRUG-GM2 | Yes | 8(8P) | 170(58P) | 148 | 5 | 5 |  |
| PMA1--D1 |  | 28(25P) | 190(8P) | 167 | 18 | 18 | 99 |
| Stauro--2Res2a |  | 28(22P) | 161(14P) | 155 | 11 | 11 | 96 |
| Stauro--3Res2a |  | 31(19P) | 155(22P) | 146 | 21 | 21 | 79 |
| TCMDC124263--11-R3a |  | 34(20P) | 145(10P) | 132 | 22 | 22 | 67 |
| TCMDC124263--3-R3a |  | 15(11P) | 46(8P) | 50 | 10 | 10 | 19 |
| Tav--8Res2b |  | 32(22P) | 192(14P) | 160 | 23 | 23 | 99 |
| Tavabarole-9Res2c |  | 39(28P) | 209(17P) | 161 | 28 | 28 | 104 |
| Wortmannin-13R3a |  | 17(14P) | 95(10P) | 85 | 13 | 13 | 35 |
| Wortmannin-17-R3a |  | 27(18P) | 171(8P) | 143 | 18 | 18 | 85 |
| Z46108311--2R2c |  | 14(9P) | 58(8P) | 60 | 9 | 9 | 27 |

*PASS counts in parentheses. Union=SURVIVOR merge (min_callers=1), Consensus=min_callers=2, Both=SUPP_VEC=11.*

## 5. CN Matrices

Dual CN matrices generated in `output_ottilie_tier2/cn_matrices/`:
- `cn_bins_continuous.csv`
- `cn_chr_summary_sensitive.csv`
- `cn_chr_summary_stringent.csv`
- `cn_segments_sensitive.csv`
- `cn_segments_stringent.csv`
- `cn_sensitive_vs_stringent.csv`

---
*Report generated by `validate_all.py`*
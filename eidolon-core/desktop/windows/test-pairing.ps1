# ==========================================================
# Projet      : Eidolon Core
# Organisation: Eidolon Core Technologies (ECT)
# Fichier     : test-pairing.ps1
# Description : Synthetic Windows DPAPI roundtrip and destination isolation
# Standard    : Eidolon Presentation Standard v1
# ==========================================================
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'eidolon-open.ps1')
$key='ecc_'+('A'*43)
$binding='fixture@127.0.0.1|8767|/private/fixture'
$encrypted=Protect-EidolonPairing $key $binding
if ($encrypted.Contains($key)) { throw 'Plain credential persisted' }
if ((Read-EidolonPairing $encrypted $binding) -cne $key) { throw 'DPAPI roundtrip failed' }
$refused=$false
try { [void](Read-EidolonPairing $encrypted ($binding+'-other')) } catch { $refused=$true }
if (-not $refused) { throw 'Wrong destination accepted' }
$refused=$false
try { [void](Read-EidolonPairing 'invalid' $binding) } catch { $refused=$true }
if (-not $refused) { throw 'Invalid cipher accepted' }
foreach ($bad in @('','ecc_bad',($key+"`n"),($key+'A'))) {
    if (Test-EidolonKey $bad) { throw 'Invalid key accepted' }
}
Write-Output 'PASS: DPAPI roundtrip, no plaintext, binding and invalid input refusal.'

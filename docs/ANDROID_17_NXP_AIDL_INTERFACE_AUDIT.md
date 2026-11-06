# AOSP17 PE-Reborn — row 169: NXP vendor NFC interface modernisation

**Audit:** 2026-11-07. **Target:** independently developed PixelExperience-Reborn Android 17, initially platform-only, future device POCO F5 Pro / Redmi K60 (`mondrian`, SM8475).

**Decision:** Keep the official Android17 NFC Mainline, system `android.hardware.nfc` AIDL and official `platform/hardware/nxp/nfc` as the active source owners. The historical `vendor/nxp/opensource/interfaces/nfc` must **not** be activated. For a verified NXP controller/vendor firmware need, evaluate NXP's current Android17 `vendor.nxp.nxpnfc_aidl` stable AIDL instead of reviving archived HIDL versions, while ensuring it is not already owned/provided by the official AOSP17 NFC HAL source. No source override, new service or hardware feature is enabled by this audit.

## Pinned historical source — why not modern

PixelExperience-Reborn `vendor_nxp_opensource_interfaces_nfc` branch `seventeen`, last commit 2020-09-03, commit `6b30fe8b2fba967bc2f00bb191d57ef420c789f9`, Git tree `90c93ca528a04310c833187c873e29aba919237f`.

- Root `Android.bp` declares `hidl_package_root` for `vendor.nxp.hardware.nfc` and `vendor.nxp.nxpnfclegacy`, but its listed `subdirs = ["1.0","1.1"]` does **not** itself include `2.0` or `nxpnfclegacy`; do not infer they are all built/enabled simply because their files exist. Soong package traversal requires verification of actual include rules/roots.
- `1.0/INqNfc.hal`: `vendor.nxp.hardware.nfc@1.0::INqNfc` with arbitrary `ioctl(uint64_t,...)`. `1.1/INqNfc.hal`: get controller chip ID and firmware revision.
- `2.0/INqNfc.hal` has `getVendorParam`, `setVendorParam`, `resetEse`, `setEseUpdateState`, `setNxpTransitConfig`, JCOP and Load/Store update checks; `2.0/Android.bp` generates Java HIDL, with `system_ext_specific: true`.
- `nxpnfclegacy/1.0/INxpNfcLegacy.hal` exposes low-level SPI/DWP synchronization, set service PID, cached NFCC configuration and unrestricted-looking `nciTransceive`; **do not automatically expose raw controller/APDU operations**.
- `current.txt` and `nxpnfclegacy/current.txt` are historical HIDL hashes, not proof of Android17 AIDL stability, VINTF compliance or on-device installed instances.

## Exact contemporary upstream NXP interface — Android 17

Verified project: [NXPNFCProject/nfcandroid_nfc_hidlimpl](https://github.com/NXPNFCProject/nfcandroid_nfc_hidlimpl/tree/br_ar_17_aosp_mainline), branch `br_ar_17_aosp_mainline`, commit `debec247cea5570d259db3138124201e3769a728`, Git tree `31be748946aaf58dcf86034804db69c53a4ac3a7`, committed 2026-07-01. Upstream's README labels release **17.07.00**, Android `android-17.0.0_r1`, controller families PN557/PN560/SN100/SN110/SN220/SN300. This is a vendor-supported *family list*, not a demonstrated mondrian part or firmware selection.

**Actual modern source:**
- `intf/nxpnfc/aidl/Android.bp`: `aidl_interface { name: "vendor.nxp.nxpnfc_aidl", vendor_available: true, stability: "vintf", frozen: true, owner: "nxp", versions_with_info: [{version: "1"...}] }`. Native `ndk` backend is available to platform and `com.android.nfcservices` APEX; C++ and Java backends are disabled. This is an AIDL V1 vendor **extension**, distinct from **system NFC AIDL V2**.
- `intf/nxpnfc/aidl/aidl_api/vendor.nxp.nxpnfc_aidl/1/.../INxpNfc.aidl`: exactly four methods `getVendorParam`, `setVendorParam`, `resetEse`, `setNxpTransitConfig`; no generic arbitrary HIDL `ioctl`, old JCOP/LS or raw NCI passthrough exposed here.
- `snxxx/aidl/2.0/nfc2-service-nxp.xml` declares **two distinct** VINTF AIDL instances: `android.hardware.nfc` version **2**, `INfc/default`; `vendor.nxp.nxpnfc_aidl` `INxpNfc/default`. This is one NFC HAL + one optional NXP extension, **not two platform NFC HALs**.
- `snxxx/aidl/2.0/main.cpp` starts both the NXP extension and system NFC HAL services using native Binder, checks dynamic HAL and wired SE mode.
- `snxxx/extns/impl/nxpnfc/aidl/NxpNfc.cpp` shows the real vendor extension implementation. `setVendorParam` affects vendor properties, `resetEse` touches SE state, and transit configuration writes vendor behavior. Verify service caller identity/SELinux access policies before exposing these methods; stable AIDL does not automatically mean the operations are safe for all callers.
- Contemporary source *also* contains historical HIDL 2.0 under `intf/nxpnfc/2.0`; not every HIDL file in a modern branch is the preferred active HAL. Selection requires Soong/service and actual product VINTF verification.
- AOSP `platform/hardware/nxp/nfc` is already in the reviewed `android-17.0.0_r1` manifest, with separate `platform/packages/modules/Nfc` and `platform/system/secure_element`. The private NXP repo is used for comparing evolution and checking source symmetry, not added as a redundant tree.

## Important distinction: system NFC vs vendor extension

| Interface/role | Correct modern owner | Review outcome |
| --- | --- | --- |
| System NFC HAL `android.hardware.nfc.INfc/default` | Android17 `hardware/interfaces` stable AIDL; service source in `hardware/nxp/nfc` | **Retain official**, validate version 2, vendor service, FCM/VINTF and physical controller |
| Vendor NFC extension `vendor.nxp.nxpnfc_aidl.INxpNfc/default` | NXP/current vendor-specific NFC HAL source when required | **Candidate**: frozen VINTF-stable AIDL v1 with NDK backend, restrict consumers/access, avoid dual instances |
| NFC framework, NFC JNI, card routing, WLC | `packages/modules/Nfc` Android17 Mainline | **Retain official**, no old NQNfcNci or historical libnfc/HIDL injection |
| eSE/OMAPI APDU and secure routing | `system/secure_element` + actual vendor service and proprietary controller/eSE firmware | **Independent gate**, vendor reset is privileged; no speculative JCOP/LS updates |
| Old `vendor.nxp.hardware.nfc@1.x/@2.0` / `vendor.nxp.nxpnfclegacy@1.0` | Archived PE source | **Do not activate**, unless device-specific vendor ELF/HIDL manifests prove a currently necessary distinct ABI, followed by narrowly scoped compatibility and compliance tests |
| Newer NXP 17.07.00 sources/firmware | Exact upstream release and verified device controller revision | **Review current source**, do not flash unknown firmware or transplant controller configuration |

## AOSP17 comparison resolved by live source CI

The official `android-17.0.0_r1` tree `platform/hardware/nxp/nfc` (commit `68931d93d3b2ccfc71553cb03088fe5d6fb5dd30`, tree `8386a3c67e07f5fe492c92d1888c256bbc37d48b`) **already declares** `vendor.nxp.nxpnfc_aidl` with VINTF stability and the exact four modern vendor API methods. Its interface source is `intf/nxpnfc/aidl/vendor/nxp/nxpnfc_aidl/INxpNfc.aidl`. This was asserted against an immutable official Git checkout by [GitHub Actions #42310830612](https://github.com/PixelExperience-Reborn/vendor_nxp_opensource_interfaces_nfc/actions/runs/42310830612), **SUCCESS**, together with exact current NXP 17.07.00 and 2020 historical HIDL pins and **27/27 manifest tests PASS**.

**Therefore the modern AIDL contract is already available in the AOSP17 source baseline. No additional modern NXP fork or legacy vendor/nxp interface checkout is required.** New NXP features, if any, should be evaluated as a *precisely scoped change against the existing official hardware/nxp/nfc checkout*, not by adding another module namespace or service registration. The selected product must still choose and build the appropriate AIDL service generation; source presence does not mean this device already runs it.

This CI outcome is only source ownership/API evidence; it did **not** prove Soong compilation, actual vendor package installation, VINTF/SEPolicy compliance, service caller authorization, NFC firmware compatibility, Secure Element or physical mondrian operation.

## Security, power and device-quality acceptance

1. **Exact hardware identity**: identify the actual mondrian NFC NFCC, firmware, eSE/UICC routing and SKU; do not assume PN81T/SN100/PN7160 from an unrelated ROM or NXP README.
2. **No duplicate service**: exactly one system `INfc/default`; if needed, exactly one vendor `INxpNfc/default` with appropriate VINTF and system/vendor file contexts, service installation, SELinux and Binder access control.
3. **Freeze/compat**: compare frozen AIDL hash/API/NDK version, `aidl_interface` module name across AOSP17 and NXP. Do not combine incompatible frozen V1/V2/V3 binaries or overwrite AOSP module namespace without rigorous ABI review.
4. **No unsafe API**: `setVendorParam`, `resetEse`, `setNxpTransitConfig` require narrowly authorized callers; no general-app privileged NFC extension, blanket SELinux allows, permissive mode or undocumented APDU access.
5. **Base independence**: LF52406 LineageOS-derived device trees remain *optional last-resort read-only hardware evidence*, not an implementation/product basis. Any useful patch must be rewritten/adapted against independent AOSP17 device structures, with credit and tests.
6. **Full validation still OPEN**: Soong/NDK AIDL version resolution, NFC Mainline/APEX update/signature contract, vendor HAL+eSE implementation, VINTF/FCM, SELinux enforcing/neverallow, CTS/VTS, NFC/HCE/secure element, recovery/suspend/OTA, battery/latency and on-device mondrian tests.

## CI scope

Isolated branch provides source-only pinned historical NXP vs **current Android17 NXP AIDL** and **official AOSP17 HAL ownership** checks. Manifest working branch forbids archived NXP path/name; two adversarial tests verify path injection and an attempted takeover of the official `hardware/nxp/nfc` checkout.

These checks do **not** build, install, invoke Binder services, modify firmware, enable NFC features or declare a boot-ready ROM.

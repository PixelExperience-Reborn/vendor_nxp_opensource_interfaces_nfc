#!/usr/bin/env python3
"""Row 169: source-only pin+consumer/ownership tests, NOT an Android17 build."""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

LEGACY = "6b30fe8b2fba967bc2f00bb191d57ef420c789f9"
LEGACY_TREE = "90c93ca528a04310c833187c873e29aba919237f"
NXP_17 = "debec247cea5570d259db3138124201e3769a728"
NXP_17_TREE = "31be748946aaf58dcf86034804db69c53a4ac3a7"
AOSP_17 = "68931d93d3b2ccfc71553cb03088fe5d6fb5dd30"
AOSP_17_TREE = "8386a3c67e07f5fe492c92d1888c256bbc37d48b"
LEGACY_PATH = "vendor/nxp/opensource/interfaces/nfc"
LEGACY_NAME = "vendor_nxp_opensource_interfaces_nfc"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args],
        text=True, stderr=subprocess.PIPE).strip()


def show(root, revision, path):
    return git(root, "show", f"{revision}:{path}")


def pin(root, ref, sha, tree, label):
    commit = git(root, "rev-parse", f"{ref}^{{commit}}")
    require(commit == sha, f"{label} unexpected SHA: {commit}")
    actual_tree = git(root, "rev-parse", f"{commit}^{{tree}}")
    require(actual_tree == tree, f"{label} unexpected tree: {actual_tree}")
    return commit


def archived_interface(root):
    ref = pin(root, "refs/remotes/origin/seventeen",
              LEGACY, LEGACY_TREE, "2020 legacy HIDL NFC")
    bp = show(root, ref, "Android.bp")
    v1 = show(root, ref, "1.0/INqNfc.hal")
    v11 = show(root, ref, "1.1/INqNfc.hal")
    v2 = show(root, ref, "2.0/INqNfc.hal")
    v2_bp = show(root, ref, "2.0/Android.bp")
    legacy = show(root, ref, "nxpnfclegacy/1.0/INxpNfcLegacy.hal")
    require('subdirs = [\n    "1.0",\n    "1.1",\n]' in bp,
            "old root subdir/module exposure changed; investigate")
    require('name: "vendor.nxp.hardware.nfc"' in bp
            and 'name: "vendor.nxp.nxpnfclegacy"' in bp
            and "hidl_package_root" in bp,
            "legacy HIDL package root changed")
    require("package vendor.nxp.hardware.nfc@1.0;" in v1
            and "ioctl(uint64_t ioctlType" in v1,
            "legacy arbitrary HIDL ioctl missing/changed")
    for api in ("getNfcChipId()", "getNfcFirmwareVersion()"):
        require(api in v11, "old HIDL 1.1 API changed: " + api)
    require('name: "vendor.nxp.hardware.nfc@2.0"' in v2_bp
            and "gen_java: true" in v2_bp,
            "old HIDL 2.0 Soong generation changed")
    for api in ("getVendorParam(", "setVendorParam(", "resetEse(",
                "setEseUpdateState(", "isJcopUpdateRequired()",
                "isLsUpdateRequired()"):
        require(api in v2, "old HIDL 2.0 API changed: " + api)
    for api in ("nciTransceive(", "spiDwpSync(", "setNfcServicePid("):
        require(api in legacy, "old raw controller/DWP interface changed: " + api)
    print("PASS: archived 2020 NXP HIDL 1.x/2.0 and nxpnfclegacy contracts pinned")
    print("PASS: old root subdirs expose only 1.0 and 1.1, not proof of enabled 2.0")


def modern_nxp(root):
    ref = pin(root, "refs/remotes/origin/br_ar_17_aosp_mainline",
              NXP_17, NXP_17_TREE, "NXP upstream Android17 17.07.00")
    api_bp = show(root, ref, "intf/nxpnfc/aidl/Android.bp")
    api = show(root, ref, "intf/nxpnfc/aidl/vendor/nxp/nxpnfc_aidl/INxpNfc.aidl")
    frozen = show(root, ref, "intf/nxpnfc/aidl/aidl_api/vendor.nxp.nxpnfc_aidl/1/vendor/nxp/nxpnfc_aidl/INxpNfc.aidl")
    manifest = ET.fromstring(show(root, ref, "snxxx/aidl/2.0/nfc2-service-nxp.xml"))
    service = show(root, ref, "snxxx/aidl/2.0/main.cpp")
    impl = show(root, ref, "snxxx/extns/impl/nxpnfc/aidl/NxpNfc.cpp")
    readme = show(root, ref, "README.md")

    require('name: "vendor.nxp.nxpnfc_aidl"' in api_bp
            and 'stability: "vintf"' in api_bp
            and "frozen: true" in api_bp
            and 'version: "1"' in api_bp
            and '"com.android.nfcservices"' in api_bp
            and "ndk: {" in api_bp, "modern NXP stable AIDL contract changed")
    require('package vendor.nxp.nxpnfc_aidl;' in api
            and "@VintfStability" in api, "modern vendor AIDL identity changed")
    expected = ["getVendorParam(", "setVendorParam(", "resetEse(",
                "setNxpTransitConfig("]
    for method in expected:
        require(method in api and method in frozen,
                "modern or frozen AIDL method missing: " + method)
    require("getNfcChipId(" not in api and "nciTransceive(" not in api,
            "modern extension unexpectedly exposes legacy HIDL/IOCTL methods")
    hals = manifest.findall("hal")
    require(len(hals) == 2 and
            {(h.findtext("name"), h.findtext("fqname"))
             for h in hals} == {
                ("android.hardware.nfc", "INfc/default"),
                ("vendor.nxp.nxpnfc_aidl", "INxpNfc/default")
            }, "NXP AIDL VINTF instance declarations changed")
    system_hal = next(h for h in hals if h.findtext("name") == "android.hardware.nfc")
    require(system_hal.findtext("version") == "2"
            and all(h.get("format") == "aidl" for h in hals),
            "modern NXP system NFC is not the AIDL V2 HAL")
    require("startNxpNfcAidlService()" in service
            and "AServiceManager_addService" in service,
            "modern NXP native Binder service registration changed")
    for fn in expected:
        require("NxpNfc::" + fn in impl,
                "modern vendor AIDL service implementation missing " + fn)
    require("17.07.00" in readme and "android-17.0.0_r1" in readme,
            "NXP Android17 release documentation drift")
    print("PASS: NXP 17.07.00 frozen vendor NDK AIDL v1 and actual implementation")
    print("PASS: NFC AIDL V2 + vendor INxpNfc/default VINTF distinct instances")
    print("OPEN: exact device vendor firmware, permission/SELinux access and HAL ABI")


def official_aosp17(root):
    ref = pin(root, "refs/tags/android-17.0.0_r1",
              AOSP_17, AOSP_17_TREE, "official AOSP17 hardware/nxp/nfc")
    files = git(root, "ls-tree", "-r", "--name-only", ref).splitlines()
    require("snxxx/Android.bp" in files,
            "official AOSP17 NFC Soong service source missing")
    bp = show(root, ref, "snxxx/Android.bp")
    require("android.hardware.nfc-service.nxp" in bp,
            "official AOSP17 NXP NFC AIDL service missing/renamed")
    # Probe, rather than assert specific vendor AIDL version. Official source
    # may already provide it, in which case adding the NXP fork duplicates it.
    vendor_iface = [p for p in files if p.endswith("nxpnfc/aidl/Android.bp")]
    require(len(vendor_iface) <= 1, "multiple AOSP17 NXP vendor interfaces")
    if vendor_iface:
        official_bp = show(root, ref, vendor_iface[0])
        require('name: "vendor.nxp.nxpnfc_aidl"' in official_bp
                and 'stability: "vintf"' in official_bp,
                "official AOSP17 NXP vendor AIDL module changed")
        print("PASS: official AOSP17 HAL already owns NXP vendor VINTF-stable AIDL")
    else:
        print("INFO: no matching official vendor AIDL module at old NXP path")
        print("OPEN: independent AOSP17 Soong/device consumer and exact owner")
    print("PASS: exact AOSP17 NXP HAL source and service owner verified")


def manifest_source_graph(root):
    root = Path(root)
    entry = ET.parse(root / "default.xml").getroot()
    require(len(entry) == 1 and entry[0].get("name") ==
            "aosp17_pe_p2_kernel_configs.xml", "unsafe default manifest owner")
    base = ET.parse(root / "aosp17_pe_bootstrap.xml").getroot()
    projects = {p.get("path"): p.get("name") for p in base.findall("project")}
    require(projects.get("hardware/nxp/nfc") == "platform/hardware/nxp/nfc",
            "official NXP AIDL HAL source replaced")
    require(projects.get("packages/modules/Nfc") == "platform/packages/modules/Nfc",
            "official NFC Mainline source replaced")
    require(projects.get("system/secure_element") == "platform/system/secure_element",
            "official Secure Element source replaced")
    require(LEGACY_PATH not in projects and LEGACY_NAME not in projects.values(),
            "archived NXP HIDL checkout unexpectedly active")
    validator = (root / "tools/validate_aosp17_base_profiles.py").read_text()
    tests = (root / "tools/test_aosp17_manifest_entrypoint.py").read_text()
    require(f'if "{LEGACY_PATH}" in projects:' in validator
            and f'"{LEGACY_NAME}"' in validator,
            "row 169 legacy checkout path/name guard not installed")
    for test in ("test_archived_nxp_hidl_interfaces_cannot_enter_android17",
                 "test_archived_nxp_hidl_must_not_replace_current_nxp_hal"):
        require(f"def {test}(" in tests, "row 169 guard regression missing: " + test)
    subprocess.run(
        [sys.executable, str(root / "tools/validate_aosp17_base_profiles.py")],
        cwd=root, check=True)
    print("PASS: AOSP17 official source ownership and 25 manifest profiles retained")


def main():
    require(len(sys.argv) == 5,
            "Usage: check_nxp_nfc_aidl_boundary.py OLD_NXP MODERN_NXP AOSP_NXP MANIFEST")
    old, modern, aosp, manifest = [Path(p).resolve() for p in sys.argv[1:]]
    require(all(p.is_dir() for p in (old, modern, aosp, manifest)),
            "missing one or more input checkouts")
    archived_interface(old)
    modern_nxp(modern)
    official_aosp17(aosp)
    manifest_source_graph(manifest)
    print("PASS: row 169 independent NFC vendor AIDL boundary source audit")
    print("NOT TESTED: Soong/NDK AIDL runtime, VINTF, SELinux or physical mondrian")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, ET.ParseError,
            subprocess.CalledProcessError) as exc:
        print("FAIL:", exc, file=sys.stderr)
        sys.exit(1)

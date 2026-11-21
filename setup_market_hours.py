from setuptools import setup

APP = ["market_menubar.py"]
DATA_FILES = [("", ["market_hours.py", "menubar_icon.png"])]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "menubar_icon.png",
    "plist": {
        "CFBundleName": "Market Hours",
        "CFBundleDisplayName": "Market Hours",
        "CFBundleIdentifier": "com.manish.market-hours",
        "CFBundleShortVersionString": "1.0.4",
        "CFBundleVersion": "1.0.4",
        "LSMinimumSystemVersion": "13.0",
        "LSUIElement": True,
        "NSUserNotificationsUsageDescription": (
            "Market Hours sends alerts 30 minutes before each market opens or closes."
        ),
    },
    "packages": ["rumps", "UserNotifications"],
    "includes": ["market_hours"],
    "excludes": ["setuptools", "pip", "pkg_resources"],
}

setup(
    name="Market Hours",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)

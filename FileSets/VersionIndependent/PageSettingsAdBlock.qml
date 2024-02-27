import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("AdBlock Settings")

    property bool isCurrentItem: root.ListView.isCurrentItem
    property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"
    property string servicePrefix: "com.victronenergy.adblock"

    function getSettingsBind(param)
    {
        return Utils.path(settingsPrefix, param)
    }

function downloadAdList() {
    var process = Qt.createQmlObject('import QtQml 2.2; import QtQuick 2.0; QtObject { property var process: Process {}}', root);
    process.process = Qt.createQmlObject('import QtQml.Models 2.3; Process {}', root);
    process.process.program = "/usr/bin/python3"; // Achten Sie darauf, den korrekten Pfad zu Python anzugeben
    process.process.arguments = ["/data/AdBlockSettings/Scripts/AdBlock.py", "--download"];
    process.process.start();
}

function applySettings() {
    var process = Qt.createQmlObject('import QtQml 2.2; import QtQuick 2.0; QtObject { property var process: Process {}}', root);
    process.process = Qt.createQmlObject('import QtQml.Models 2.3; Process {}', root);
    process.process.program = "/usr/bin/python3"; // Achten Sie darauf, den korrekten Pfad zu Python anzugeben
    process.process.arguments = ["/data/AdBlockSettings/Scripts/AdBlock.py", "--configure"];
    process.process.start();
}

    model: VisibleItemModel {
        MbSwitch {
            id: adBlockEnabledSwitch
            name: qsTr("Enable AdBlock")
            bind: Utils.path(settingsPrefix, "/Enabled")
        }

        MbSwitch {
            id: dhcpEnabledSwitch
            name: qsTr("Enable DHCP")
            bind: Utils.path(settingsPrefix, "/DHCPEnabled")
        }

        MbSwitch {
            id: ipv6EnabledSwitch
            name: qsTr("Enable IPv6")
            bind: Utils.path(settingsPrefix, "/IPv6Enabled")
        }

        MbEditBox {
            id: iPRangeStartBox
            description: qsTr("IP Range Start")
            maximumLength: 20
            item.bind: getSettingsBind("/IPRangeStart")
        }

        MbEditBox {
            id: iPRangeEndBox
            description: qsTr("IP Range End")
            maximumLength: 20
            item.bind: getSettingsBind("/IPRangeEnd")
        }

        MbEditBox {
            id: defaultGatewayBox
            description: qsTr("Default Gateway")
            maximumLength: 20
            item.bind: getSettingsBind("/DefaultGateway")
        }

        MbEditBox {
            id: adListURLBox
            description: qsTr("AdListURL")
            maximumLength: 100
            item.bind: getSettingsBind("/AdListURL")
        }

        MbOK {
            id: downloadHostsButton
            description: ""
            value: qsTr ("Download Hosts")
			onClicked: downloadAdList()
        }

        MbItemOptions {
            id: updateIntervalOption
            description: qsTr("BlockListUpdateInterval")
            bind: Utils.path(settingsPrefix, "/UpdateInterval")
            possibleValues: [
                MbOption { description: qsTr("Täglich"); value: "daily" },
                MbOption { description: qsTr("Wöchentlich"); value: "weekly" },
                MbOption { description: qsTr("Monatlich"); value: "monthly" }
            ]
        }

        MbOK {
            id: uebernehmenButton
            description: ""
            value: qsTr ("Übernehmen")
			onClicked: applySettings()
        }
    }
}

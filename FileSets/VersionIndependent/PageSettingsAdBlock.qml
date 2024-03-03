import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("AdBlock Settings")

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"
    property string servicePrefix: "com.victronenergy.adblock"

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
            item.bind: Utils.path(settingsPrefix, "/IPRangeStart")
        }

        MbEditBox {
            id: iPRangeEndBox
            description: qsTr("IP Range End")
            maximumLength: 20
            item.bind: Utils.path(settingsPrefix, "/IPRangeEnd")
        }

        MbEditBox {
            id: defaultGatewayBox
            description: qsTr("Default Gateway")
            maximumLength: 20
            item.bind: Utils.path(settingsPrefix, "/DefaultGateway")
        }

        MbEditBox {
            id: adListURLBox
            description: qsTr("AdList URL")
            maximumLength: 100
            item.bind: Utils.path(settingsPrefix, "/AdListURL")
        }

        MbItemOptions {
            id: updateIntervalOption
            description: qsTr("BlockList Update Interval")
            bind: Utils.path(settingsPrefix, "/UpdateInterval")
            possibleValues: [
                MbOption { description: qsTr("Daily"); value: "daily" },
                MbOption { description: qsTr("Weekly"); value: "weekly" },
                MbOption { description: qsTr("Monthly"); value: "monthly" }
            ]
        }

    MbOK {
        id: downloadButton  // ID hinzugefügt
        description: qsTr("Download Hosts")
        value: qsTr("Download")
        onClicked: {
            adBlockDownloadTrigger.setValue(true);
        }
    }

    MbOK {
        id: applyButton  // ID hinzugefügt
        description: qsTr("Apply Settings")
        value: qsTr("Apply")
        onClicked: {
            adBlockApplySettingsTrigger.setValue(true);
        }
    }
}

    VBusItem { id: adBlockDownloadTrigger; bind: Utils.path(servicePrefix, "/DownloadTrigger") }
    VBusItem { id: adBlockApplySettingsTrigger; bind: Utils.path(servicePrefix, "/ConfigureTrigger") }
}

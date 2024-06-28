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
            description: qsTr("Default Gateway (Router)")
            maximumLength: 20
            item.bind: Utils.path(settingsPrefix, "/DefaultGateway")
        }

        MbEditBox {
            id: dnsServer
            description: qsTr("DNS Server")
            maximumLength: 20
            item.bind: Utils.path(settingsPrefix, "/DNSServer")
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
            id: downloadButton
            description: adBlockDownloading.value ? qsTr("Downloading...") : qsTr("Download Hosts")
            value: qsTr("Download")
            onClicked: {
                adBlockDownloadTrigger.setValue(true);
            }
        }

        MbOK {
            id: applyButton
            description: adBlockConfiguring.value ? qsTr("Applying...") : qsTr("Apply Settings")
            value: qsTr("Apply")
            onClicked: {
                adBlockApplySettingsTrigger.setValue(true);
            }
        }

        MbButton {
            description: qsTr("Manage Blocklist URLs")
            onClicked: {
                pageStack.push(Qt.resolvedUrl("PageBlocklistURLs.qml"))
            }
        }

        MbButton {
            description: qsTr("Manage Whitelist")
            onClicked: {
                pageStack.push(Qt.resolvedUrl("PageWhitelist.qml"))
            }
        }

        MbButton {
            description: qsTr("Manage Blacklist")
            onClicked: {
                pageStack.push(Qt.resolvedUrl("PageBlacklist.qml"))
            }
        }
    }

    VBusItem { id: adBlockDownloadTrigger; bind: Utils.path(servicePrefix, "/DownloadTrigger") }
    VBusItem { id: adBlockApplySettingsTrigger; bind: Utils.path(servicePrefix, "/ConfigureTrigger") }
    VBusItem { id: adBlockDownloading; bind: Utils.path(servicePrefix, "/Downloading") }
    VBusItem { id: adBlockConfiguring; bind: Utils.path(servicePrefix, "/Configuring") }
}

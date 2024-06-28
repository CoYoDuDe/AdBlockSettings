import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("AdBlock Blocklist URLs")

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"
    property string servicePrefix: "com.victronenergy.adblock"

    property bool isCurrentItem: root.ListView.isCurrentItem
    property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

    model: VisibleItemModel {
        MbEditBox {
            id: adBlockBlocklistEntry
            description: qsTr("Enter Blocklist URL")
            maximumLength: 100
            item.bind: Utils.path(settingsPrefix, "/AdBlockURLs")
        }

        MbOK {
            id: addButton
            description: qsTr("Add to Blocklist")
            value: qsTr("Add")
            onClicked: {
                // Logik zum Hinzufügen der eingegebenen URL zur Blockliste
            }
        }
    }
}

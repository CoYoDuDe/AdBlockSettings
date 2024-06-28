import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("AdBlock Blacklist")

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"
    property string servicePrefix: "com.victronenergy.adblock"

    property bool isCurrentItem: root.ListView.isCurrentItem
    property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

    model: VisibleItemModel {
        MbEditBox {
            id: adBlockBlacklistEntry
            description: qsTr("Enter Blacklist Domain")
            maximumLength: 100
            item.bind: Utils.path(settingsPrefix, "/AdBlockBlacklist")
        }

        MbOK {
            id: addButton
            description: qsTr("Add to Blacklist")
            value: qsTr("Add")
            onClicked: {
                // Logic to add the entered domain to the blacklist
            }
        }
    }
}

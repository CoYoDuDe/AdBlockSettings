import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("Whitelist")

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"

    model: VisibleItemModel {
        Repeater {
            model: whitelistModel
            delegate: MbEditBox {
                description: qsTr("Whitelist Entry")
                maximumLength: 100
                item.bind: whitelistModel.get(index).entry
            }
        }

        MbButton {
            description: qsTr("Add Entry")
            onClicked: {
                whitelistModel.append({"entry": ""})
            }
        }
    }

    ListModel {
        id: whitelistModel
        ListElement { entry: "" } // Initial empty entry
    }
}

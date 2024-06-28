import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("Blacklist")

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"

    model: VisibleItemModel {
        Repeater {
            model: blacklistModel
            delegate: MbEditBox {
                description: qsTr("Blacklist Entry")
                maximumLength: 100
                item.bind: blacklistModel.get(index).entry
            }
        }

        MbButton {
            description: qsTr("Add Entry")
            onClicked: {
                blacklistModel.append({"entry": ""})
            }
        }
    }

    ListModel {
        id: blacklistModel
        ListElement { entry: "" } // Initial empty entry
    }
}

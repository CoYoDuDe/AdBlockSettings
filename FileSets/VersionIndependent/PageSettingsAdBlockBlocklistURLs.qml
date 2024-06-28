import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("Blocklist URLs")

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"

    model: VisibleItemModel {
        Repeater {
            model: urlModel
            delegate: MbEditBox {
                description: qsTr("Blocklist URL")
                maximumLength: 100
                item.bind: urlModel.get(index).url
            }
        }

        MbButton {
            description: qsTr("Add URL")
            onClicked: {
                urlModel.append({"url": ""})
            }
        }
    }

    ListModel {
        id: urlModel
        ListElement { url: "" } // Initial empty entry
    }
}

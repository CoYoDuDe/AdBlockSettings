import QtQuick 1.1
import "utils.js" as Utils
import com.victron.velib 1.0

MbPage {
    id: root
    title: qsTr("AdBlock URLs")

    property string settingsPrefix: "com.victronenergy.settings/Settings/AdBlock"
    property string servicePrefix: "com.victronenergy.adblock"

    property bool isCurrentItem: root.ListView.isCurrentItem
    property MbStyle style: MbStyle { isCurrentItem: root.ListView.isCurrentItem }

    ListModel {
        id: urlModel
    }

    Component.onCompleted: {
        // Load the initial URLs from the DBus settings
        VBusItem {
            id: adBlockUrlItem
            bind: Utils.path(settingsPrefix, "/AdBlockURLs")
            onValueChanged: {
                urlModel.clear();
                if (adBlockUrlItem.valid && adBlockUrlItem.value.length > 0) {
                    var urls = adBlockUrlItem.value.split("\n");
                    for (var i = 0; i < urls.length; i++) {
                        urlModel.append({"url": urls[i]});
                    }
                }
            }
        }
    }

    Column {
        Repeater {
            model: urlModel
            delegate: MbEditBox {
                width: parent.width
                description: qsTr("AdBlock URL")
                maximumLength: 100
                item.value: model.url
                onTextChanged: {
                    urlModel.setProperty(index, "url", item.value);
                }
            }
        }

        MbEditBox {
            id: newUrlEntry
            width: parent.width
            description: qsTr("Enter new AdBlock URL")
            maximumLength: 100
        }

        MbOK {
            id: addButton
            width: parent.width
            description: qsTr("Add to AdBlock URLs")
            value: qsTr("Add")
            onClicked: {
                if (newUrlEntry.item.value.length > 0) {
                    urlModel.append({"url": newUrlEntry.item.value});
                    newUrlEntry.item.value = "";
                    updateAdBlockUrls();
                }
            }
        }
    }

    function updateAdBlockUrls() {
        var urls = [];
        for (var i = 0; i < urlModel.count; i++) {
            urls.push(urlModel.get(i).url);
        }
        adBlockUrlItem.setValue(urls.join("\n"));
    }
}

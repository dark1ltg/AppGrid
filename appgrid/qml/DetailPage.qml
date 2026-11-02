import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import "."

Page {
    id: page
    signal back()
    background: Rectangle { color: "#12151C" }

    Dialog {
        id: removeConfirm
        title: "Remove this app?"
        modal: true
        standardButtons: Dialog.Cancel | Dialog.Ok
        font.family: Fonts.sans
        font.pixelSize: Fonts.button
        font.weight: Fonts.medium
        Label {
            text: controller.selectedCopyCount > 1
                  ? "Remove " + controller.selectedName + "? Every installed copy will be removed."
                  : "Remove " + controller.selectedName + "?"
            wrapMode: Text.WordWrap
            width: 420
            font.family: Fonts.sans
            font.pixelSize: Fonts.settings
            font.weight: Fonts.regular
        }
        onOpened: {
            var ok = standardButton(Dialog.Ok)
            if (ok)
                ok.text = "Remove"
        }
        onAccepted: controller.removeSelected()
    }

    Dialog {
        id: installConfirm
        title: "Install newer copy?"
        modal: true
        standardButtons: Dialog.Cancel | Dialog.Ok
        font.family: Fonts.sans
        font.pixelSize: Fonts.button
        font.weight: Fonts.medium
        Label {
            text: {
                var src = controller.selectedBackend === "flatpak" ? "Flatpak" : "APT"
                return "Install " + src + " " + controller.selectedName
                       + "? The older installed copy will stay until you Remove."
            }
            wrapMode: Text.WordWrap
            width: 420
            font.family: Fonts.sans
            font.pixelSize: Fonts.settings
            font.weight: Fonts.regular
        }
        onOpened: {
            var ok = standardButton(Dialog.Ok)
            if (ok)
                ok.text = "Install"
        }
        onAccepted: controller.installSelected()
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 24

            ColumnLayout {
                Layout.preferredWidth: 520
                Layout.fillHeight: true
                Layout.fillWidth: false
                spacing: 10

                Button {
                    id: backButton
                    Accessible.name: "Back"
                    Layout.alignment: Qt.AlignLeft
                    Layout.preferredHeight: 36
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.button
                    font.weight: Fonts.medium
                    onClicked: page.back()
                    background: Rectangle {
                        radius: 8
                        color: backButton.hovered ? "#243044" : "transparent"
                    }
                    contentItem: Row {
                        spacing: 6
                        Text {
                            text: "←"
                            color: "#F2F6FB"
                            font.family: Fonts.sans
                            font.pixelSize: Fonts.heading
                            font.weight: Fonts.medium
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            text: "Back"
                            color: "#F2F6FB"
                            font: backButton.font
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 520
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    radius: 16
                    color: controller.selectedAccent
                    clip: true

                Image {
                    anchors.fill: parent
                    source: controller.selectedScreenshot
                    fillMode: Image.PreserveAspectCrop
                    visible: controller.selectedScreenshot !== ""
                    asynchronous: true
                }

                Image {
                    anchors.fill: parent
                    source: controller.selectedIcon
                    fillMode: Image.PreserveAspectCrop
                    visible: controller.selectedScreenshot === "" && controller.selectedIcon !== ""
                    asynchronous: true
                }

                Column {
                    visible: controller.selectedScreenshot === "" && controller.selectedIcon === ""
                    anchors.centerIn: parent
                    spacing: 8
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: controller.selectedInitial
                        color: "white"
                        font.family: Fonts.sans
                        font.pixelSize: 48
                        font.weight: Fonts.bold
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: controller.selectedName
                        color: "#F4F7FB"
                        font.family: Fonts.sans
                        font.pixelSize: Fonts.heading
                        font.weight: Fonts.bold
                    }
                }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 360
                spacing: 10

                Item {
                    Layout.preferredHeight: 36
                    Layout.fillWidth: true
                }

                Label {
                    text: controller.selectedName
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.heading
                    font.weight: Fonts.bold
                    color: "#F2F6FB"
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Rectangle {
                    visible: controller.selectedCategory !== ""
                    Layout.alignment: Qt.AlignHCenter
                    implicitWidth: categoryLabel.implicitWidth + 16
                    implicitHeight: 24
                    radius: 12
                    color: "#243044"
                    Text {
                        id: categoryLabel
                        anchors.centerIn: parent
                        text: controller.selectedCategory
                        color: "#D5DEE8"
                        font.family: Fonts.sans
                        font.pixelSize: Fonts.chip
                        font.weight: Fonts.medium
                    }
                }
                Label {
                    visible: controller.selectedDeveloper !== ""
                    text: "by " + controller.selectedDeveloper
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.description
                    font.weight: Fonts.regular
                    color: "#9AA8BA"
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Label {
                    text: controller.selectedSummary
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.description
                    font.weight: Fonts.regular
                    color: "#C5D0DF"
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Label {
                    visible: controller.selectedRating > 0
                    text: "★ " + Number(controller.selectedRating).toFixed(1)
                    color: "#E8C547"
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.rating
                    font.weight: Fonts.regular
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Label {
                    text: controller.selectedStatusLabel
                    color: controller.selectedInstalled
                           || controller.activeAction !== "" ? "#6FCFC6" : "#9AA8BA"
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.status
                    font.weight: Fonts.medium
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Label {
                    visible: controller.selectedVersion !== ""
                    text: controller.selectedVersion
                    color: "#9AA8BA"
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.description
                    font.weight: Fonts.regular
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                }
                Button {
                    visible: controller.selectedPrimaryAction !== ""
                    text: controller.selectedPrimaryAction === "update" ? "Update" : "Install"
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.settings
                    font.weight: Fonts.medium
                    enabled: !controller.busy && controller.selectedUid !== ""
                    Layout.fillWidth: true
                    Layout.preferredHeight: 44
                    highlighted: true
                    Material.background: "#2A6F6A"
                    Material.foreground: "#F2F6FB"
                    background: Rectangle {
                        radius: 8
                        color: parent.down ? "#245E59" : "#2A6F6A"
                        opacity: parent.enabled ? 1 : 0.45
                    }
                    contentItem: Text {
                        text: parent.text
                        font: parent.font
                        color: "#F2F6FB"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    onClicked: {
                        if (controller.selectedPrimaryAction === "update")
                            controller.updateSelected()
                        else if (controller.selectedInstallOverCopy)
                            installConfirm.open()
                        else
                            controller.installSelected()
                    }
                }
                Item {
                    visible: controller.selectedCanRemove
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    Button {
                        id: removeButton
                        anchors.horizontalCenter: parent.horizontalCenter
                        text: "Remove"
                        font.family: Fonts.sans
                        font.pixelSize: Fonts.button
                        font.weight: Fonts.medium
                        enabled: !controller.busy && controller.selectedUid !== ""
                        height: 36
                        width: contentItem.implicitWidth + leftPadding + rightPadding
                        leftPadding: 14
                        rightPadding: 14
                        onClicked: removeConfirm.open()
                        background: Rectangle {
                            radius: 8
                            color: removeButton.hovered ? "#332028" : "transparent"
                            border.width: 1
                            border.color: removeButton.hovered ? "#A85C5C" : "#4A5564"
                        }
                        contentItem: Text {
                            text: removeButton.text
                            font: removeButton.font
                            color: removeButton.hovered ? "#E8A0A0" : "#C5D0DF"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }
                ScrollView {
                    id: descScroll
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    contentWidth: availableWidth
                    Label {
                        width: descScroll.availableWidth
                        text: controller.selectedDescription
                        horizontalAlignment: Text.AlignLeft
                        wrapMode: Text.WordWrap
                        textFormat: Text.PlainText
                        color: "#B7C4D2"
                        font.family: Fonts.sans
                        font.pixelSize: Fonts.description
                        font.weight: Fonts.regular
                    }
                }
            }
        }
    }
}

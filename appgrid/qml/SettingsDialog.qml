import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import "."

Dialog {
    id: dialog
    title: "Settings"
    modal: true
    standardButtons: Dialog.Close
    width: 480
    font.family: Fonts.sans
    font.pixelSize: Fonts.settings
    font.weight: Fonts.regular
    Material.background: "#1A1F29"
    Material.foreground: "#E8EDF4"

    onOpened: {
        var closeBtn = standardButton(Dialog.Close)
        if (closeBtn) {
            closeBtn.font.family = Fonts.sans
            closeBtn.font.pixelSize = Fonts.button
            closeBtn.font.weight = Fonts.medium
        }
    }

    ColumnLayout {
        spacing: 16
        width: parent ? parent.width : 440

        Switch {
            id: flatpakSwitch
            text: "Enable Flatpak"
            font.family: Fonts.sans
            font.pixelSize: Fonts.settings
            font.weight: Fonts.regular
            checked: controller.flatpakEnabled
            onClicked: {
                if (checked === controller.flatpakEnabled)
                    return
                controller.setFlatpakEnabled(checked)
            }
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#A8B3C7"
            font.family: Fonts.sans
            font.pixelSize: Fonts.settings
            font.weight: Fonts.regular
            text: "Off: install from " + controller.nativeStoreLabel + " only. On: Flathub is included too, still one card per app. The card face is the newer copy — " + controller.nativeStoreLabel + " when that version is newer or the same, Flatpak when Flathub is newer. Install installs that newer copy even if an older one is already installed."
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: "#A8B3C7"
            font.family: Fonts.sans
            font.pixelSize: Fonts.settings
            font.weight: Fonts.regular
            text: "If a Flatpak cannot open files, folders, or devices, install Flatseal and grant it the access it needs."
        }
    }
}

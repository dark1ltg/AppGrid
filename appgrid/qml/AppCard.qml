import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

Item {
    id: card
    signal clicked()

    property bool thumbOk: fallback.status === Image.Ready
    property bool iconOk: iconShot.status === Image.Ready

    Rectangle {
        anchors.fill: parent
        radius: 14
        color: "#1C2330"
        border.color: installed ? "#3D9B93" : "#2A3344"
        border.width: installed ? 2 : 1

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            spacing: 8

            Rectangle {
                id: frame
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumHeight: 96
                radius: 10
                color: "#10141C"
                clip: true

                Image {
                    id: fallback
                    anchors.fill: parent
                    source: thumb
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    visible: thumb !== "" && thumbOk
                }

                Image {
                    id: iconShot
                    anchors.fill: parent
                    source: icon
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    cache: true
                    visible: !thumbOk && iconOk
                }

                Rectangle {
                    anchors.fill: parent
                    visible: !thumbOk && !iconOk
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Qt.lighter(accent, 1.18) }
                        GradientStop { position: 1.0; color: accent }
                    }

                    Column {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: initial
                            color: "#FFFFFF"
                            font.family: Fonts.sans
                            font.pixelSize: Fonts.heading
                            font.weight: Fonts.bold
                        }
                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            text: name
                            color: "#F2F6FB"
                            font.family: Fonts.sans
                            font.pixelSize: Fonts.chip
                            font.weight: Fonts.medium
                        }
                    }
                }

                Rectangle {
                    visible: controller.showSourceBadges
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.margins: 8
                    width: badge.implicitWidth + 14
                    height: 22
                    radius: 11
                    color: "#CC12151C"
                    z: 2
                    Text {
                        id: badge
                        anchors.centerIn: parent
                        text: backend === "flatpak" ? "FLATPAK" : "APT"
                        color: "#F4F7FB"
                        font.family: Fonts.mono
                        font.pixelSize: Fonts.monoSize
                        font.weight: Fonts.regular
                    }
                }

                Rectangle {
                    visible: hasUpdate
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 8
                    width: 70
                    height: 22
                    radius: 11
                    color: "#D98A2B"
                    z: 2
                    Text {
                        anchors.centerIn: parent
                        text: "UPDATE"
                        color: "white"
                        font.family: Fonts.sans
                        font.pixelSize: Fonts.badge
                        font.weight: Fonts.bold
                    }
                }
            }

            Label {
                text: name
                color: "#F2F6FB"
                font.family: Fonts.sans
                font.pixelSize: Fonts.appName
                font.weight: Fonts.medium
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.preferredHeight: Fonts.appName + 4
            }

            Label {
                text: rating > 0 ? "★ " + Number(rating).toFixed(1) : " "
                color: "#E8C547"
                opacity: rating > 0 ? 1 : 0
                font.family: Fonts.sans
                font.pixelSize: Fonts.rating
                font.weight: Fonts.regular
                Layout.preferredHeight: Fonts.rating + 2
            }

            Label {
                text: summary
                color: "#9AA8BA"
                font.family: Fonts.sans
                font.pixelSize: Fonts.description
                font.weight: Fonts.regular
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.preferredHeight: Math.ceil(Fonts.description * 2.6)
                Layout.maximumHeight: Math.ceil(Fonts.description * 2.6)
            }

            Label {
                text: installed
                    ? (hasUpdate ? "Installed · update available" : "Installed")
                    : (controller.showSourceBadges ? origin : " ")
                color: installed ? "#6FCFC6" : "#7E8B9A"
                opacity: (installed || controller.showSourceBadges) ? 1 : 0
                font.family: Fonts.sans
                font.pixelSize: Fonts.status
                font.weight: installed ? Fonts.medium : Fonts.regular
                elide: Text.ElideRight
                Layout.fillWidth: true
                Layout.preferredHeight: Fonts.status + 2
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        cursorShape: Qt.PointingHandCursor
        onClicked: card.clicked()
    }
}

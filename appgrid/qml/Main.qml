import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import "."

ApplicationWindow {
    id: root
    visible: true
    width: 1280
    height: 860
    title: "AppGrid"
    color: "#12151C"
    property bool categoryBannerOpen: false
    property string shotDetailUid: ""
    font.family: Fonts.sans
    font.pixelSize: Fonts.nav
    font.weight: Fonts.medium
    Material.theme: Material.Dark
    Material.accent: "#3D9B93"
    Material.background: "#12151C"
    Material.foreground: "#E8EDF4"

    header: ToolBar {
        Material.background: "#1A1F29"
        height: 64
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 16
            spacing: 16

            Label {
                text: "AppGrid"
                font.family: Fonts.sans
                font.pixelSize: Fonts.heading
                font.weight: Fonts.bold
                color: "#F2F6FB"
            }

            TextField {
                id: search
                Layout.fillWidth: true
                Layout.preferredHeight: 40
                placeholderText: "Search applications"
                font.family: Fonts.sans
                font.pixelSize: Fonts.nav
                font.weight: Fonts.regular
                onTextChanged: controller.setSearch(text)
            }

            Button {
                id: categoryButton
                enabled: controller.supportedDistro
                text: controller.categoryFilter === "" ? "Categories" : categoryButton.currentLabel
                font.family: Fonts.sans
                font.pixelSize: Fonts.button
                font.weight: Fonts.medium
                readonly property string currentLabel: {
                    var items = controller.categories
                    for (var i = 0; i < items.length; i++) {
                        if (items[i].id === controller.categoryFilter)
                            return items[i].label
                    }
                    return "Categories"
                }
                Material.background: (root.categoryBannerOpen || controller.categoryFilter !== "") ? "#2A6F6A" : "#243044"
                onClicked: root.categoryBannerOpen = !root.categoryBannerOpen
            }

            Repeater {
                model: [
                    { id: "all", label: "All" },
                    { id: "installed", label: "Installed" },
                    { id: "updates", label: "Updates" }
                ]
                delegate: Button {
                    text: modelData.label
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.button
                    font.weight: Fonts.medium
                    checkable: true
                    checked: controller.filterMode === modelData.id
                    onClicked: controller.setFilter(modelData.id)
                    Material.background: checked ? "#2A6F6A" : "#243044"
                }
            }

            Button {
                text: "Settings"
                font.family: Fonts.sans
                font.pixelSize: Fonts.button
                font.weight: Fonts.medium
                onClicked: settingsDialog.open()
            }

            Button {
                text: "Update system"
                font.family: Fonts.sans
                font.pixelSize: Fonts.button
                font.weight: Fonts.medium
                enabled: !controller.busy && controller.supportedDistro
                onClicked: controller.updateAll()
            }
        }
    }

    footer: ToolBar {
        Material.background: "#151A22"
        height: 44
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            Label {
                text: controller.status
                color: "#A8B3C7"
                font.family: Fonts.sans
                font.pixelSize: Fonts.description
                font.weight: Fonts.regular
                Layout.fillWidth: true
            }
            Button {
                text: "Cancel"
                font.family: Fonts.sans
                font.pixelSize: Fonts.button
                font.weight: Fonts.medium
                visible: controller.busy && controller.supportedDistro
                onClicked: controller.cancelJob()
            }
            Item {
                id: busyBadge
                visible: controller.busy
                implicitWidth: 32
                implicitHeight: 32
                BusyIndicator {
                    anchors.fill: parent
                    running: controller.busy
                }
                Label {
                    anchors.centerIn: parent
                    visible: controller.progressKnown
                    text: controller.progressPercent + "%"
                    color: "#F2F6FB"
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.badge
                    font.weight: Fonts.medium
                }
            }
        }
    }

    SettingsDialog {
        id: settingsDialog
        objectName: "settingsDialog"
    }

    StackView {
        id: stack
        anchors.fill: parent
        initialItem: gridPage
    }

    Component {
        id: gridPage
        Item {
            id: gridPageRoot
            readonly property int gridMargin: 18
            readonly property int minCell: 228
            readonly property int minCellH: 278
            readonly property int tickerMax: 52
            readonly property var tickerSource: {
                var items = [{ "id": "all", "label": "All" }]
                var cats = controller.categories
                for (var i = 0; i < cats.length; i++)
                    items.push(cats[i])
                return items.concat(items)
            }
            readonly property int available: Math.max(minCell, width - gridMargin * 2)
            readonly property int availableH: Math.max(minCellH, height - gridMargin * 2 - tickerBar.height)
            readonly property int columns: Math.max(1, Math.floor(available / minCell))
            readonly property int cellW: Math.floor(available / columns)
            readonly property int sidePad: Math.floor((available - cellW * columns) / 2)
            readonly property int rows: Math.max(1, Math.ceil(Math.max(controller.countVisible, 1) / columns))
            readonly property int rowsFit: Math.max(1, Math.floor(availableH / minCellH))
            readonly property bool fillHeight: controller.countVisible > 0 && rows <= rowsFit
            readonly property int cellH: fillHeight ? Math.floor(availableH / rows) : minCellH
            readonly property int vPad: fillHeight ? Math.floor((availableH - cellH * rows) / 2) : 0

            Rectangle {
                id: tickerBar
                z: 2
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: root.categoryBannerOpen && controller.supportedDistro ? gridPageRoot.tickerMax : 0
                clip: true
                color: "#151A22"
                Behavior on height {
                    NumberAnimation {
                        duration: 240
                        easing.type: Easing.OutCubic
                    }
                }

                onHeightChanged: {
                    if (height >= gridPageRoot.tickerMax - 1 && tickerRow.width > 1) {
                        tickerAnim.to = -(tickerRow.width / 2)
                        tickerAnim.restart()
                    }
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: "#2A3344"
                    visible: tickerBar.height > 1
                }

                Item {
                    id: tickerClip
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    clip: true
                    visible: tickerBar.height > 8

                    Row {
                        id: tickerRow
                        y: (parent.height - height) / 2
                        spacing: 10

                        Repeater {
                            model: gridPageRoot.tickerSource
                            delegate: Rectangle {
                                height: 32
                                width: chipLabel.implicitWidth + 28
                                radius: 16
                                color: ((modelData.id === "all" && controller.categoryFilter === "")
                                        || modelData.id === controller.categoryFilter) ? "#2A6F6A" : "#243044"
                                border.width: 1
                                border.color: ((modelData.id === "all" && controller.categoryFilter === "")
                                               || modelData.id === controller.categoryFilter) ? "#3D9B93" : "#2A3344"
                                Text {
                                    id: chipLabel
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    color: "#F2F6FB"
                                    font.family: Fonts.sans
                                    font.pixelSize: Fonts.chip
                                    font.weight: Fonts.medium
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: controller.setCategory(modelData.id)
                                }
                            }
                        }
                    }

                    NumberAnimation {
                        id: tickerAnim
                        target: tickerRow
                        property: "x"
                        from: 0
                        to: tickerRow.width > 0 ? -(tickerRow.width / 2) : 0
                        duration: Math.max(14000, tickerRow.width * 12)
                        loops: Animation.Infinite
                        running: root.categoryBannerOpen && tickerBar.height > 40 && !tickerHover.hovered
                        easing.type: Easing.Linear
                    }

                    HoverHandler {
                        id: tickerHover
                    }
                }

                Rectangle {
                    width: 56
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    visible: tickerBar.height > 8
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "#151A22" }
                        GradientStop { position: 1.0; color: "#00151A22" }
                    }
                }
                Rectangle {
                    width: 56
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    visible: tickerBar.height > 8
                    gradient: Gradient {
                        orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "#00151A22" }
                        GradientStop { position: 1.0; color: "#151A22" }
                    }
                }
            }

            GridView {
                id: grid
                anchors.fill: parent
                anchors.leftMargin: gridPageRoot.gridMargin + gridPageRoot.sidePad
                anchors.topMargin: tickerBar.height + gridPageRoot.gridMargin + gridPageRoot.vPad
                anchors.bottomMargin: gridPageRoot.fillHeight
                    ? gridPageRoot.gridMargin + (gridPageRoot.availableH - gridPageRoot.cellH * gridPageRoot.rows - gridPageRoot.vPad)
                    : gridPageRoot.gridMargin
                anchors.rightMargin: gridPageRoot.gridMargin + (gridPageRoot.available - gridPageRoot.cellW * gridPageRoot.columns - gridPageRoot.sidePad)
                cellWidth: gridPageRoot.cellW
                cellHeight: gridPageRoot.cellH
                clip: true
                visible: controller.supportedDistro
                model: appModel
                delegate: AppCard {
                    width: gridPageRoot.cellW - 16
                    height: gridPageRoot.cellH - 12
                    onClicked: {
                        controller.select(uid)
                        stack.push(detailPage)
                    }
                }
                ScrollBar.vertical: ScrollBar {}
            }

            Label {
                anchors.centerIn: parent
                width: parent.width - 80
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                visible: !controller.supportedDistro
                text: controller.unsupportedMessage
                color: "#C5D0DF"
                font.family: Fonts.sans
                font.pixelSize: Fonts.settings
                font.weight: Fonts.regular
            }

            Label {
                anchors.centerIn: parent
                visible: controller.supportedDistro && controller.countVisible === 0 && !controller.busy
                text: "No applications match this view"
                color: "#7E8B9A"
                font.family: Fonts.sans
                font.pixelSize: Fonts.settings
                font.weight: Fonts.regular
            }

            Label {
                anchors.centerIn: parent
                visible: controller.supportedDistro && controller.busy && controller.countVisible === 0
                text: "Loading apps…"
                color: "#7E8B9A"
                font.family: Fonts.sans
                font.pixelSize: Fonts.settings
                font.weight: Fonts.regular
            }
        }
    }

    Component {
        id: detailPage
        DetailPage {
            onBack: {
                controller.clearSelection()
                stack.pop()
            }
        }
    }

    onShotDetailUidChanged: {
        if (shotDetailUid === "")
            return
        controller.select(shotDetailUid)
        stack.push(detailPage)
    }
}

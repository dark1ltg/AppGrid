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
        height: 92
        // Explicit fill — Material.background alone can fail to paint the strip.
        background: Rectangle { color: "#1A1F29" }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20
            anchors.rightMargin: 16
            anchors.topMargin: 8
            anchors.bottomMargin: 8
            spacing: 12

            Label {
                text: "AppGrid"
                font.family: Fonts.sans
                font.pixelSize: Fonts.heading
                font.weight: Fonts.bold
                color: "#F2F6FB"
                Layout.alignment: Qt.AlignVCenter
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                TextField {
                    id: search
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    placeholderText: "Search applications"
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.nav
                    font.weight: Fonts.regular
                    color: "#F2F6FB"
                    placeholderTextColor: "#7E8B9A"
                    background: Rectangle {
                        radius: 8
                        color: "#12151C"
                        border.width: 1
                        border.color: "#2A3344"
                    }
                    onTextChanged: controller.setSearch(text)
                }

                Button {
                    id: categoryButton
                    enabled: controller.supportedDistro
                    Layout.fillWidth: true
                    Layout.preferredHeight: 30
                    text: {
                        if (controller.categoryFilter !== "")
                            return "Showing: " + categoryButton.currentLabel
                        return root.categoryBannerOpen ? "Browse by categories ▾" : "Browse by categories"
                    }
                    font.family: Fonts.sans
                    font.pixelSize: Fonts.chip
                    font.weight: Fonts.medium
                    readonly property string currentLabel: {
                        var items = controller.categories
                        for (var i = 0; i < items.length; i++) {
                            if (items[i].id === controller.categoryFilter)
                                return items[i].label
                        }
                        return "All"
                    }
                    background: Rectangle {
                        radius: 6
                        color: (root.categoryBannerOpen || controller.categoryFilter !== "") ? "#2A6F6A" : "#243044"
                        border.width: 1
                        border.color: (root.categoryBannerOpen || controller.categoryFilter !== "") ? "#3D9B93" : "#2A3344"
                    }
                    contentItem: Text {
                        text: categoryButton.text
                        font: categoryButton.font
                        color: "#F2F6FB"
                        horizontalAlignment: Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                        leftPadding: 10
                        elide: Text.ElideRight
                    }
                    onClicked: root.categoryBannerOpen = !root.categoryBannerOpen
                }
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
                    Layout.alignment: Qt.AlignVCenter
                    onClicked: controller.setFilter(modelData.id)
                    Material.background: checked ? "#2A6F6A" : "#243044"
                }
            }

            Button {
                text: "Settings"
                font.family: Fonts.sans
                font.pixelSize: Fonts.button
                font.weight: Fonts.medium
                Layout.alignment: Qt.AlignVCenter
                onClicked: settingsDialog.open()
            }

            Button {
                text: "Update system"
                font.family: Fonts.sans
                font.pixelSize: Fonts.button
                font.weight: Fonts.medium
                enabled: !controller.busy && controller.supportedDistro
                Layout.alignment: Qt.AlignVCenter
                onClicked: controller.updateAll()
            }
        }
    }

    footer: ToolBar {
        id: statusBar
        height: 44
        // Explicit fill — Material.background alone blends into the page and
        // hides the strip→footer gap the facts bar is meant to match.
        background: Rectangle {
            color: "#151A22"
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: 1
                color: "#2A3344"
            }
        }
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
                text: "Reload"
                font.family: Fonts.sans
                font.pixelSize: Fonts.button
                font.weight: Fonts.medium
                visible: !controller.busy && controller.supportedDistro
                onClicked: controller.reload()
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
            // One chip row (no duplicated marquee loop). Clear filter is appended in the strip.
            readonly property var tickerSource: {
                var items = [{ "id": "all", "label": "All" }]
                var cats = controller.categories
                for (var i = 0; i < cats.length; i++)
                    items.push(cats[i])
                return items
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

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: "#2A3344"
                    visible: tickerBar.height > 1
                }

                Flickable {
                    id: tickerFlick
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    contentWidth: tickerRow.width
                    contentHeight: height
                    clip: true
                    interactive: tickerRow.width > width
                    boundsBehavior: Flickable.StopAtBounds
                    visible: tickerBar.height > 8
                    flickableDirection: Flickable.HorizontalFlick

                    Row {
                        id: tickerRow
                        y: (tickerFlick.height - height) / 2
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

                        // Last chip: reset to All and close the strip.
                        Rectangle {
                            height: 32
                            width: clearChipLabel.implicitWidth + 28
                            radius: 16
                            color: "#243044"
                            border.width: 1
                            border.color: "#3D9B93"
                            Text {
                                id: clearChipLabel
                                anchors.centerIn: parent
                                text: "Clear filter"
                                color: "#F2F6FB"
                                font.family: Fonts.sans
                                font.pixelSize: Fonts.chip
                                font.weight: Fonts.medium
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    controller.setCategory("all")
                                    root.categoryBannerOpen = false
                                }
                            }
                        }
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

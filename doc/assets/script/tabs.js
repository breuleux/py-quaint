
function show_tab(tabs, elems, j) {
    return function() {
        for (var i = 0; i < tabs.children.length; i++) {
            if (i == j) {
                tabs.children[i].className = "active";
                elems.children[i].style.display = "block";
            }
            else {
                tabs.children[i].className = "";
                elems.children[i].style.display = "none";
            }
        }
    };
}

function convert_tabdiv(tabdiv) {
    var tabs = tabdiv.children[0];
    var elems = tabdiv.children[1];
    tabs.className = "tabs";
    for (var i = 0; i < tabs.children.length; i++)
        tabs.children[i].onclick = show_tab(tabs, elems, i);
    show_tab(tabs, elems, 0)();
}

function convert_all_tabdivs(classname) {
    var elements = document.getElementsByClassName(classname)
    for (var i = 0; i < elements.length; i++)
        convert_tabdiv(elements[i]);
}




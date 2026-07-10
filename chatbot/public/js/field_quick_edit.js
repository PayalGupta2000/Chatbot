frappe.ui.form.on("DocField", {
    refresh(frm) {
        frm.fields_dict.__details.$wrapper.append(`
            <div class="checkbox">
                <label>
                    <input type="checkbox" id="allow_quick_edit"
                        ${frm.doc.allow_quick_edit ? "checked" : ""}>
                    Allow Quick Edit
                </label>
            </div>
        `);

        $("#allow_quick_edit").on("change", function () {
            frm.set_value("allow_quick_edit", this.checked ? 1 : 0);
        });
    }
});
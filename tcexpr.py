#!/usr/bin/env python
#-*- encoding: utf-8 -*-

#import os
#os.environ.setdefault('LANG', 'en')

import pygtk,glib,gtk,sys
pygtk.require('2.0')
if gtk.pygtk_version < (2,4,0):
    print >> sys.stderr,"PyGtk 2.4.0 or later required"
    raise SystemExit(1)
gtk.gdk.threads_init()

import threading,subprocess,pexpect,sys,gettext

from event.listeners import *
from object.schema import *
from exception.exceptions import *

class ThreadApplySchema(threading.Thread):
    ''' Schema application thread
    '''
    returncode = 0
    errmsg = ''

    def __init__(self, schema, parentWindow):
        threading.Thread.__init__(self)
        self.schema = schema
        self.pwin = parentWindow

    def run(self):
        me = self.schema.getMySelf()
        fsrv = self.schema.getFileSrv(False)
        fsrvstr = "%s:%s" % (fsrv[COL_HOST], fsrv[COL_IP])
        others = self.schema.servers[:]
        others.remove(me)
        srvlst = ["%s:%s" % (srv[COL_HOST],srv[COL_IP]) for srv in others]
        curdir = os.path.abspath(os.curdir)
        absscript = "/bin/bash \"%s/cluster.sh\"" % curdir
        if me[COL_COMBO_KEY] == 'filesrv':
            cmd = "%s -m filesvr -d %s -s %s" % (absscript, me[COL_PATH], ','.join(srvlst))
            self.__exec(cmd)
        elif me[COL_COMBO_KEY] == 'master':
            if me is fsrv:
                cmd = "%s -m filesvr -s %s" % (absscript, ','.join(srvlst))
                self.__exec(cmd)
            else:
                cmd = "%s -m backbone -d %s -s %s" % (absscript, me[COL_PATH], fsrvstr)
                self.__execWithPswd(cmd)
        elif me[COL_COMBO_KEY] == 'slave':
            mstr = self.schema.getMasterSrv()
            cmd = "%s -m slave -d %s -s %s -b %s" % (absscript, me[COL_PATH], fsrvstr, mstr[COL_IP])
            self.__execWithPswd(cmd)
        else:
            pass
        glib.idle_add(self.pwin.spinner.destroy)

    def __exec(self, cmd):
        print sys._getframe().f_code.co_name,cmd
        p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        errmsg = p.communicate()[1]
        if p.returncode is not 0:
            self.returncode = p.returncode
            self.errmsg = errmsg
            return False
        return True

    def __execWithPswd(self, cmd):
        print sys._getframe().f_code.co_name,cmd
        p = pexpect.spawn(cmd)
        while True:
            j = p.expect(['.*(yes/no).*', '.*password:.*', 'Permission denied.*', pexpect.EOF, pexpect.TIMEOUT])
            if j == 0:
                p.sendline('yes')
            elif j == 1:
                p.sendline(self.schema.getFileSrvPswd())
            elif j == 2:
                self.returncode = 1
                self.errmsg = 'Permission denied.'
                p.close()
                return False
            elif j == 3:
                if p.exitstatus is not 0:
                    self.returncode = p.exitstatus
                    self.errmsg = p.before
                    return False
                return True
            elif j == 4:
                self.returncode = 1
                self.errmsg = 'Timeout.'
                p.close()
                return False

class PyApp(gtk.Window):
    version = 1.0
    emptyRow = ('', '', '', '', '', True, True)
    schema = Schema()
    restart = False
    __ui = """
    <ui>
        <menubar name="MenuBar">
            <menu action="File">
                <menuitem action="Open"/>
                <menuitem action="Save"/>
                <separator/>
                <menuitem action="Exit"/>
            </menu>
            <menu action="Edit">
                <menuitem action="AddServer"/>
                <menuitem action="DropServer"/>
                <menuitem action="ValidateSchema"/>
                <menuitem action="ApplySchema"/>
            </menu>
            <menu action="BackupRestore">
                <menuitem action="Backup"/>
                <menuitem action="Restore"/>
            </menu>
            <menu action="Help">
                <menuitem action="About"/>
            </menu>
        </menubar>
    </ui>
    """

    serverTypes = [
        ('filesrv', 'File Server'),
        ('master', 'Master'),
        ('slave', 'Slave'),
    ]

    def __init__(self):
        super(PyApp, self).__init__()
        self.connect("destroy", self.onDestroy)
        self.set_size_request(640, 480)
        self.set_position(gtk.WIN_POS_CENTER)

        uimanager = gtk.UIManager()
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)
        uimanager.add_ui_from_string(self.__ui)
        self.actiongroup = gtk.ActionGroup("MenuActionGroup")
        self.actiongroup.add_actions([
            ("File", None, _('_File')), 
            ("Open", gtk.STOCK_OPEN, _("_Open"), None, "Open an Existing Document", self.onOpen),
            ("Save", gtk.STOCK_SAVE, _("_Save"), None, "Save the Current Document", self.onSave),
            ("Exit", gtk.STOCK_QUIT, _("_Exit"), None, "Quit the Application", self.onDestroy),
            ("Edit", None, _("_Edit")),
            ("AddServer", gtk.STOCK_ADD, _("_Add Server"), None, "Add a new row", self.onAddServer),
            ("DropServer", gtk.STOCK_DELETE, _("_Delete Server"), None, "Drop the selected row", self.onDropServer),
            ("ValidateSchema", gtk.STOCK_OK, _("_Validate Schema"), None, "Validate the current schema", self.onValidateSchema),
            ("ApplySchema", gtk.STOCK_APPLY, _("_Apply Schema"), None, "Apply the current schema", self.onApplySchema),
            ("BackupRestore", None, _("_Backup & Restore")),
            ("Backup", gtk.STOCK_FLOPPY, _("Backup _Cluster Files"), None, "Backup cluster files", self.todo),
            ("Restore", gtk.STOCK_REVERT_TO_SAVED, _("_Restore Cluster Files"), None, "Restore cluster files", self.todo),
            ("Help", None, _("_Help")),
            ("About", gtk.STOCK_ABOUT, _("_About"), None, "The about dialog", self.showAboutDialog),
        ])
        uimanager.insert_action_group(self.actiongroup, 0)

        vbox = gtk.VBox(False, 2)

        mb = uimanager.get_widget("/MenuBar")
        vbox.pack_start(mb, False, False, 0)

        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.pack_start(sw, True, True, 0)

        treeModel = self.createModel()
        self.treeView = gtk.TreeView(treeModel)
        #treeView.connect("row-activated", self.on_activated)
        self.treeView.set_rules_hint(True)
        sw.add(self.treeView)
        self.createColumns(self.treeView)

        hbox = gtk.HBox(True, 3)
        btn = gtk.Button(_('_Add Server'))
        btn.connect("clicked", self.onAddServer)
        hbox.add(btn)
        btn = gtk.Button(_('_Delete Server'))
        btn.connect("clicked", self.onDropServer)
        hbox.add(btn)
        btn = gtk.Button(_('Va_lidate Schema'))
        btn.connect("clicked", self.onValidateSchema)
        hbox.add(btn)
        btn = gtk.Button(_('A_pply Schema'))
        btn.connect("clicked", self.onApplySchema)
        hbox.add(btn)
        vbox.pack_start(hbox, False, False, 0)

        self.add(vbox)

        self.show_all()

    def createModel(self):
        store = gtk.ListStore(str, str, str, str, str, bool, bool)
        return store

    def createColumns(self, treeView):
        model = treeView.get_model()

        renderer = gtk.CellRendererCombo()
        typeStore = gtk.ListStore(str, str)
        for stype in self.serverTypes:
            typeStore.append(stype)
        renderer.set_property('editable', True)
        renderer.set_property('model', typeStore)
        renderer.set_property('text-column', COL_COMBO_VAL)
        renderer.connect("edited", self.onCellEdited, (model,COL_COMBO_VAL))
        column = gtk.TreeViewColumn(_("Type"), renderer, text=COL_COMBO_VAL)
        column.set_resizable(True)
        column.set_min_width(100)
        #column.set_sort_column_id(0)
        treeView.append_column(column)

        renderer = gtk.CellRendererText()
        renderer.connect("edited", self.onCellEdited, (model,COL_HOST))
        renderer.set_data("column", COL_HOST)
        column = gtk.TreeViewColumn(_("Host Name"), renderer, text=COL_HOST, editable=COL_ROW_EDITABLE)
        column.set_resizable(True)
        #column.set_sort_column_id(1)
        treeView.append_column(column)

        renderer = gtk.CellRendererText()
        renderer.connect("edited", self.onCellEdited, (model,COL_IP))
        renderer.set_data("column", COL_IP)
        column = gtk.TreeViewColumn(_("IP Address"), renderer, text=COL_IP, editable=COL_ROW_EDITABLE)
        column.set_resizable(True)
        #column.set_sort_column_id(2)
        treeView.append_column(column)

        renderer = gtk.CellRendererText()
        renderer.connect("edited", self.onCellEdited, (model,COL_PATH))
        renderer.set_data("column", COL_PATH)
        column = gtk.TreeViewColumn(_("Shared Directory"), renderer, text=COL_PATH, editable=COL_PATH_EDITABLE)
        column.set_resizable(True)
        #column.set_sort_column_id(3)
        treeView.append_column(column)

    def onCellEdited(self, cell, path, newText, userData):
        newText = newText.strip()
        store,colNum = userData
        usrData = [store, newText, path, colNum]
        if colNum == COL_COMBO_VAL:
            usrData.append(COL_COMBO_KEY)
            evt = TCSrvTypeChangedEvent(self, cell, usrData)
        elif colNum == COL_HOST:
            evt = TCHostChangedEvent(self, cell, usrData)
        elif colNum == COL_IP:
            evt = TCIPChangedEvent(self, cell, usrData)
        elif colNum == COL_PATH:
            evt = TCPathChangedEvent(self, cell, usrData)
        else:
            evt = TCUnknownCellEditedEvent(self, cell, usrData)

        TCEventQueue.fireEvent(evt)
        try:
            TCEventQueue.processEvents()
            self.schema.loadStore(store)
        except Exception,e:
            self.alert(e)
            col = self.treeView.get_column(colNum-1)
            glib.idle_add(self.treeView.set_cursor_on_cell, path, col, cell, True)

    def onAddServer(self, w=None, data=None):
        row = self.treeView.get_model().append(self.emptyRow)
        rowNum = self.treeView.get_model().get_string_from_iter(row)
        self.treeView.set_cursor(rowNum)

    def onDropServer(self, w=None, data=None):
        cursorPos = self.treeView.get_cursor()
        if cursorPos[0] is None:
            self.alert(_("Please select a row to delete !"))
            return
        rowNum = cursorPos[0][0]
        iter = self.treeView.get_model().get_iter_from_string(str(rowNum))
        self.treeView.get_model().remove(iter)
        if self.treeView.get_model().iter_is_valid(iter): self.treeView.set_cursor(str(rowNum))
        elif rowNum-1>=0: self.treeView.set_cursor(str(rowNum-1))

    def onValidateSchema(self, w=None, data=None):
        try:
            self.__validateSchema()
        except TCException, e:
            self.alert(e)
        else:
            self.info(_('Schema is valid !'))

    def __validateSchema(self):
        master = None
        filesrv = None
        slaves = []
        store = self.treeView.get_model()
        for row in store:
            if row[COL_COMBO_KEY] == 'filesrv':
                if filesrv is not None:
                    raise TCException(_('File server should not be more than one !'))
                filesrv = row
            elif row[COL_COMBO_KEY] == 'master':
                if master is not None:
                    raise TCException(_('Master server must be one, no more, no less !'))
                master = row
            elif row[COL_COMBO_KEY] == 'slave': slaves.append(row)
            else: self.alert(_('Dirty or empty row exists !'))
        # Master must exist
        if master is None:
            raise TCException(_('Master server must be one, no more, no less !'))
        # Slaves must be one or more
        if len(slaves)==0:
            raise TCException(_('Slaves are missing !'))
        # Host names must be given
        hostnames = [r[COL_HOST] for r in store]
        if hostnames.count('')>0:
            raise TCException(_('Hostnames must not be empty !'))
        # Host names must not duplicate
        hostset = set(hostnames)
        if len(hostnames) != len(hostset):
            raise TCException(_('Hostnames cannot be duplicated !'))
        # IP addresses must be given
        iplist = [r[COL_IP] for r in store]
        if iplist.count('')>0:
            raise TCException(_('IP addresses must not be empty !'))
        # IP addresses must not duplicate
        ipset = set(iplist)
        if len(iplist) != len(ipset):
            raise TCException(_('IP addresses cannot be duplicated !'))
        # Shared paths must be given
        pathlist = [r[COL_PATH] for r in store]
        if pathlist.count('')>0:
            raise TCException(_('Shared paths must not be empty !'))
        # The format of shared paths should be based upon the existence of file server and the master server
        basesrv = master
        if filesrv is not None:
            basesrv = filesrv
        if not os.path.isabs(basesrv[COL_PATH]):
            raise TCException(_('Invalid path !'))
        spath = basesrv[COL_HOST]+':'+basesrv[COL_PATH]
        if filesrv is not None and master[COL_PATH] != spath:
            raise TCException(_('Invalid path !'))
        for slave in slaves:
            if slave[COL_PATH] != spath:
                raise TCException(_('Invalid path !'))

    def onSave(self, w=None, data=None):
        try:
            self.__validateSchema()
        except TCException, e:
            self.alert(e)
            return False

        if self.schema.getPath() is None:
            dialog = gtk.FileChooserDialog(_("Open.."), None,
                gtk.FILE_CHOOSER_ACTION_SAVE,
                (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
            dialog.set_default_response(gtk.RESPONSE_OK)

            filter = gtk.FileFilter()
            filter.set_name(_("Schema"))
            filter.add_mime_type("text/scm")
            filter.add_pattern("*.scm")
            dialog.add_filter(filter)
   
            filter = gtk.FileFilter()
            filter.set_name(_("All files"))
            filter.add_pattern("*")
            dialog.add_filter(filter)

            response = dialog.run()
            if response == gtk.RESPONSE_OK:
                fname = dialog.get_filename()
                fparts = os.path.splitext(fname)
                if len(fparts[1])==0: fname = fname+'.scm'
                self.schema.setPath(fname)
            dialog.destroy()

        store = self.treeView.get_model()
        self.schema.loadStore(store)
        self.schema.save()
        self.info(_('Schema saved to %s.') % self.schema.getPath())

    def onOpen(self, w=None, data=None):
        dialog = gtk.FileChooserDialog(_("Open.."), None,
            gtk.FILE_CHOOSER_ACTION_OPEN,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OPEN, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)

        filter = gtk.FileFilter()
        filter.set_name(_("Schema"))
        filter.add_mime_type("text/scm")
        filter.add_pattern("*.scm")
        dialog.add_filter(filter)

        filter = gtk.FileFilter()
        filter.set_name(_("All files"))
        filter.add_pattern("*")
        dialog.add_filter(filter)

        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            self.schema = Schema.load(dialog.get_filename())
            cells = self.schema.servers
            store = self.treeView.get_model()
            store.clear()
            for row in cells:
                store.append(row)
        dialog.destroy()

    def onApplySchema(self, w=None, data=None):
        ''' Apply the schema to the current machine
        '''
        try:
            self.__validateSchema()
        except TCException, e:
            self.alert(e)
            return False
        # Find the current machine from the schema
        me = self.schema.getMySelf()
        if me is None:
            self.alert(_('The current machine is not in the schema !'))
            return False
        # Ask for password
        me = self.schema.getMySelf()
        fsrv = self.schema.getFileSrv()
        if (me[COL_COMBO_KEY]=='master' and me is not fsrv) or me[COL_COMBO_KEY]=='slave':
            pswd = self.__getPassword()
            self.schema.setFileSrvPswd(pswd)
        # Apply the schema
        t = ThreadApplySchema(self.schema, self)
        t.start()
        # Show spinner
        self.__showSpinner()
        # Check result
        if t.returncode is not 0:
            self.alert(t.errmsg)
        else:
            self.info(_('Job done !'))

    def __getPassword(self):
        ''' Ask the user for the password of the root user
        '''
        dlg = gtk.MessageDialog(
            None,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_OK,
            None)
        dlg.set_markup(_('Please enter <b>root</b> password:'))
        entry = gtk.Entry()
        entry.set_visibility(False)
        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_("Password:")), False, 5, 5)
        hbox.pack_end(entry)
        dlg.format_secondary_markup(_("This will be used to synchronize files to the file server."))
        dlg.vbox.pack_end(hbox, True, True, 0)
        dlg.show_all()
        dlg.run()
        text = entry.get_text()
        dlg.destroy()
        return text

    def __showSpinner(self):
        ''' Pop up a modal dialog, which has a spinner
        '''
        sprDlg = gtk.Dialog('spinner', self, \
                gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT|gtk.DIALOG_NO_SEPARATOR)
        self.spinner = sprDlg
        sprDlg.set_default_size(180,120)
        sprDlg.set_decorated(False)
        lbl = gtk.Label(_('Applying schema ...'))
        sprDlg.vbox.pack_start(lbl, True, True, 0)
        try:
            spr = gtk.Spinner()
            spr.start()
            sprDlg.vbox.pack_start(spr, True, True, 0)
        except AttributeError,e:
            print e
        sprDlg.show_all()
        sprDlg.run()
        sprDlg.destroy()

    def __restart(self):
        ''' Restart app
        '''
        self.restart = True
        self.set_opacity(0)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.onDestroy()

    def onDestroy(self, w=None, data=None):
        ''' Destroy app
        '''
        gtk.main_quit()

    def showAboutDialog(self, x):
        ''' Pop up the famous about dialog
        '''
        dlg = gtk.AboutDialog()
        dlg.set_program_name('TurboCRM Cluster Express')
        dlg.set_version(str(self.version))
        dlg.set_copyright(_('Author: Li Dong <lidonga@ufida.com>'))
        dlg.set_comments(_('Cluster configuration tool for TurboCRM'))
        dlg.set_website('http://0x3f.org')
        dlg.run()
        dlg.destroy()

    def alert(self, msg):
        ''' Show warning messages
        '''
        dlg = gtk.MessageDialog(self, gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, str(msg))
        dlg.run()
        dlg.destroy()

    def info(self, msg):
        ''' Show normal information
        '''
        dlg = gtk.MessageDialog(self, gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO, gtk.BUTTONS_OK, str(msg))
        dlg.run()
        dlg.destroy()

    def yesno(self, msg):
        ''' Ask for confirmation
        '''
        dlg = gtk.MessageDialog(self, gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, str(msg))
        decision = dlg.run()
        dlg.destroy()
        return decision

    def todo(self, w=None, data=None):
        ''' Pop up a warning dialog when clicking on an unimplemented function
        '''
        self.alert(_('Not implemented !'))

if __name__ == '__main__':
    # Initiate languages
    gettext.install('tcexpr', 'locale')
    # Run the app
    app = PyApp()
    gtk.main()

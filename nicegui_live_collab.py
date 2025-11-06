# nicegui_live_collab.py
from nicegui import ui
import hashlib
import uuid
import time
import os

# ============================================
# SHARED DATA (in-memory, lost on restart)
# ============================================
documents = {}      # {doc_id: {'text': str, 'version': int}}
active_users = {}   # {doc_id: {user_id: timestamp}}

# ============================================
# HELPER FUNCTIONS
# ============================================
def get_hash(text):
    """Quick way to check if text changed"""
    return hashlib.md5(text.encode()).hexdigest()

def cleanup_inactive_users(doc_id):
    """Remove users who haven't been seen in 5 seconds"""
    if doc_id not in active_users:
        return 0
    current_time = time.time()
    active_users[doc_id] = {uid: ts for uid, ts in active_users[doc_id].items() 
                            if current_time - ts < 5}
    return len(active_users[doc_id])

# ============================================
# DOCUMENT PAGE (the main collaboration page)
# ============================================
@ui.page('/docs/{doc_id}')
async def doc_room(doc_id: str):
    user_id = str(uuid.uuid4())[:8]  # Unique ID for this user
    
    # Initialize document if new
    if doc_id not in documents:
        documents[doc_id] = {'text': '', 'version': 0}
    if doc_id not in active_users:
        active_users[doc_id] = {}
    
    active_users[doc_id][user_id] = time.time()  # Mark user as active
    
    # ============================================
    # UI ELEMENTS
    # ============================================
    ui.label(f'Document: {doc_id}').classes('text-2xl font-bold mb-4')
    
    textarea = ui.textarea('Live document (shared)', 
                          placeholder='Start typing...').props('outlined autogrow').classes('w-full')
    textarea.value = documents[doc_id]['text']
    
    with ui.row().classes('gap-4 mt-2'):
        status = ui.label('🟢 Connected').classes('text-sm')
        user_count = ui.label('👥 Active users: 1').classes('text-sm')
    
    # ============================================
    # STATE TRACKING
    # ============================================
    state = {
        'version': documents[doc_id]['version'],
        'is_typing': False,
        'last_hash': get_hash(documents[doc_id]['text']),
        'pending_save': None
    }
    
    # ============================================
    # CORE FUNCTIONS
    # ============================================
    def save():
        """Save current text to server"""
        documents[doc_id]['text'] = textarea.value
        documents[doc_id]['version'] += 1
        state['version'] = documents[doc_id]['version']
        state['last_hash'] = get_hash(textarea.value)
        status.text = '🟢 Connected'
    
    async def sync():
        """Check for updates from others + update user count"""
        # Update this user's presence
        active_users[doc_id][user_id] = time.time()
        user_count.text = f'👥 Active users: {cleanup_inactive_users(doc_id)}'
        
        # Don't pull updates while typing
        if state['is_typing']:
            return
        
        # Pull updates if server has newer version
        if documents[doc_id]['version'] > state['version']:
            new_hash = get_hash(documents[doc_id]['text'])
            if new_hash != state['last_hash']:
                textarea.set_value(documents[doc_id]['text'])  # Use set_value() instead!
                state['version'] = documents[doc_id]['version']
                state['last_hash'] = new_hash
    
    def on_type():
        """Called every time user types a character"""
        state['is_typing'] = True
        status.text = '🟡 Typing...'
        
        # Cancel previous save timer
        if state['pending_save']:
            state['pending_save'].deactivate()
        
        # Save 200ms after user stops typing
        state['pending_save'] = ui.timer(0.2, lambda: [
            save(), 
            setattr(state, 'is_typing', False)
        ], once=True)
    
    # ============================================
    # EVENT BINDINGS
    # ============================================
    textarea.on('update:model-value', on_type)
    textarea.on('blur', lambda: [state['pending_save'] and state['pending_save'].deactivate(), 
                                  save(), setattr(state, 'is_typing', False)])
    
    ui.timer(0.1, sync)  # Check for updates every 100ms

# ============================================
# HOME PAGE
# ============================================
@ui.page('/')
def index():
    ui.label('NiceGUI Collaborative Document Editor').classes('text-3xl font-bold mb-4')
    ui.markdown('### Quick Start\nEnter a document name to create or join:')
    
    doc_input = ui.input('Document name', placeholder='e.g., meeting-notes').classes('w-full max-w-md').props('outlined')
    
    def open_doc():
        name = ''.join(c for c in (doc_input.value.strip() or 'default') if c.isalnum() or c in '-_')
        ui.navigate.to(f'/docs/{name}')
    
    ui.button('Open Document', on_click=open_doc).classes('mt-2')
    doc_input.on('keydown.enter', open_doc)
    
    # Show existing documents
    if documents:
        ui.label('Existing documents:').classes('text-xl font-bold mt-8 mb-2')
        for doc_id in documents.keys():
            with ui.card().classes('w-full max-w-md'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label(doc_id).classes('font-mono')
                    count = cleanup_inactive_users(doc_id)
                    if count > 0:
                        ui.label(f'👥 {count}').classes('text-sm text-green-600 font-bold')
                preview = documents[doc_id]['text'][:100] + ('...' if len(documents[doc_id]['text']) > 100 else '')
                ui.label(preview or '(empty)').classes('text-gray-600 text-sm')
                ui.button('Open', on_click=lambda d=doc_id: ui.navigate.to(f'/docs/{d}')).props('flat')

# ============================================
# START SERVER
# ============================================
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title='NiceGUI Live Collaboration',
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8080)),
        reload=False,
        show=False
    )
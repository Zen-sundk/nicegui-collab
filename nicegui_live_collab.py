# nicegui_live_collab.py
from nicegui import ui, app
from datetime import datetime, timedelta
import hashlib
import uuid
import time

# In-memory shared storage
documents = {}
active_users = {}  # {doc_id: {user_id: last_seen_timestamp}}

def get_hash(text):
    """Get hash of text for change detection"""
    return hashlib.md5(text.encode()).hexdigest()

def cleanup_inactive_users(doc_id):
    """Remove users who haven't been seen in 5 seconds"""
    if doc_id not in active_users:
        return 0
    
    current_time = time.time()
    active_users[doc_id] = {
        uid: last_seen 
        for uid, last_seen in active_users[doc_id].items() 
        if current_time - last_seen < 5
    }
    return len(active_users[doc_id])

@ui.page('/docs/{doc_id}')
async def doc_room(doc_id: str):
    # Generate unique user ID for this session
    user_id = str(uuid.uuid4())[:8]
    
    # Initialize document if it doesn't exist
    if doc_id not in documents:
        documents[doc_id] = {
            'text': '',
            'version': 0,
            'last_updated': datetime.now()
        }
    
    # Initialize active users tracking for this doc
    if doc_id not in active_users:
        active_users[doc_id] = {}
    
    # Add this user to active users with current timestamp
    active_users[doc_id][user_id] = time.time()
    
    ui.label(f'Document: {doc_id}').classes('text-2xl font-bold mb-4')
    
    # Create textarea
    textarea = ui.textarea(
        label='Live document (shared with all users)',
        placeholder='Start typing... Syncs in real-time'
    ).props('outlined autogrow').classes('w-full')
    
    # Set initial value
    textarea.value = documents[doc_id]['text']
    
    # Track local state
    local_state = {
        'version': documents[doc_id]['version'],
        'is_typing': False,
        'last_hash': get_hash(documents[doc_id]['text']),
        'pending_save': None
    }
    
    # Status indicators
    with ui.row().classes('gap-4 mt-2'):
        status = ui.label('🟢 Connected').classes('text-sm')
        last_sync = ui.label(f'Synced: {datetime.now().strftime("%H:%M:%S")}').classes('text-sm')
        user_count = ui.label(f'👥 Active users: 1').classes('text-sm')
    
    def save_to_server():
        """Save current content to server"""
        try:
            documents[doc_id]['text'] = textarea.value
            documents[doc_id]['version'] += 1
            documents[doc_id]['last_updated'] = datetime.now()
            
            # Update local tracking
            local_state['version'] = documents[doc_id]['version']
            local_state['last_hash'] = get_hash(textarea.value)
            
            last_sync.text = f'Synced: {datetime.now().strftime("%H:%M:%S")}'
            status.text = '🟢 Connected'
            
        except Exception as e:
            status.text = f'🔴 Error: {str(e)}'
    
    def update_presence():
        """Update this user's last seen timestamp"""
        active_users[doc_id][user_id] = time.time()
    
    async def check_for_updates():
        """Check for updates from other users"""
        try:
            # Update presence
            update_presence()
            
            # Clean up inactive users and update count
            count = cleanup_inactive_users(doc_id)
            user_count.text = f'👥 Active users: {count}'
            
            # Skip content sync if user is currently typing
            if local_state['is_typing']:
                return
            
            # Check if server version is newer
            server_version = documents[doc_id]['version']
            if server_version > local_state['version']:
                server_text = documents[doc_id]['text']
                server_hash = get_hash(server_text)
                
                # Only update if content actually changed
                if server_hash != local_state['last_hash']:
                    textarea.value = server_text
                    local_state['version'] = server_version
                    local_state['last_hash'] = server_hash
                    last_sync.text = f'Synced: {datetime.now().strftime("%H:%M:%S")}'
        except Exception as e:
            status.text = f'🔴 Error: {str(e)}'
    
    def on_input():
        """Called on every keystroke"""
        try:
            local_state['is_typing'] = True
            status.text = '🟡 Typing...'
            
            # Cancel any pending save
            if local_state['pending_save'] is not None:
                local_state['pending_save'].deactivate()
            
            # Schedule save after 200ms of no typing (FASTER!)
            local_state['pending_save'] = ui.timer(0.2, lambda: [
                save_to_server(),
                setattr(local_state, 'is_typing', False)
            ], once=True)
            
        except Exception as e:
            status.text = f'🔴 Error: {str(e)}'
    
    def on_blur():
        """When textarea loses focus, save immediately"""
        if local_state['pending_save'] is not None:
            local_state['pending_save'].deactivate()
        save_to_server()
        local_state['is_typing'] = False
    
    # Bind events
    textarea.on('update:model-value', on_input)
    textarea.on('blur', on_blur)

    # Check for updates FASTER - every 100ms instead of 200ms
    ui.timer(0.1, check_for_updates)
    
    # Instructions
    with ui.expansion('How to use', icon='info').classes('mt-4 max-w-3xl'):
        ui.markdown('''
        **Testing collaborative editing:**
        1. Share this URL with your teammates
        2. Everyone opens the same document URL
        3. Start typing - changes appear within 0.5-1 second
        
        **How it works:**
        - Your changes auto-save 0.2 seconds after you stop typing
        - Updates from others check every 0.1 seconds
        - Active user count shows everyone currently viewing (updates every 0.1s)
        - Last write wins (simple but effective)
        
        **Tips:**
        - Click outside the text box to force an immediate save
        - The sync is fast but not instant - expect ~0.5-1s delay
        - Works best when people take turns or work on different sections
        ''')

@ui.page('/')
def index():
    ui.label('NiceGUI Collaborative Document Editor').classes('text-3xl font-bold mb-4')
    
    ui.markdown('''
    ### Quick Start
    Create or join a document by entering a document name below:
    ''')
    
    doc_input = ui.input(
        label='Document name',
        placeholder='e.g., meeting-notes, project-plan'
    ).classes('w-full max-w-md').props('outlined')
    
    def open_doc():
        doc_name = doc_input.value.strip() or 'default'
        # Clean the doc name (remove special chars)
        doc_name = ''.join(c for c in doc_name if c.isalnum() or c in '-_')
        ui.navigate.to(f'/docs/{doc_name}')
    
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
                preview = documents[doc_id]['text'][:100]
                if len(documents[doc_id]['text']) > 100:
                    preview += '...'
                ui.label(preview or '(empty)').classes('text-gray-600 text-sm')
                ui.button('Open', on_click=lambda d=doc_id: ui.navigate.to(f'/docs/{d}')).props('flat')

if __name__ in {"__main__", "__mp_main__"}:
    import os
    ui.run(
        title='NiceGUI Live Collaboration',
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8080)),
        reload=False,
        show=False
    )
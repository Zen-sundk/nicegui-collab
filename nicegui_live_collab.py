# nicegui_live_collab.py
from nicegui import ui
from datetime import datetime
import hashlib

# In-memory shared storage
documents = {}

def get_hash(text):
    """Get hash of text for change detection"""
    return hashlib.md5(text.encode()).hexdigest()

@ui.page('/docs/{doc_id}')
async def doc_room(doc_id: str):
    # Initialize document if it doesn't exist
    if doc_id not in documents:
        documents[doc_id] = {
            'text': '',
            'version': 0,
            'last_updated': datetime.now()
        }
    
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
        'last_hash': get_hash(documents[doc_id]['text'])
    }
    
    # Status indicators
    with ui.row().classes('gap-4 mt-2'):
        status = ui.label('🟢 Connected').classes('text-sm')
        last_sync = ui.label(f'Synced: {datetime.now().strftime("%H:%M:%S")}').classes('text-sm')
    
    async def check_for_updates():
        """Check for updates from other users"""
        try:
            # Skip if user is currently typing
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
                    status.text = '🟢 Synced'
        except Exception as e:
            status.text = f'🔴 Error: {str(e)}'
    
    def on_change():
        """When user types, save to server immediately"""
        try:
            local_state['is_typing'] = True
            
            # Save to server
            documents[doc_id]['text'] = textarea.value
            documents[doc_id]['version'] += 1
            documents[doc_id]['last_updated'] = datetime.now()
            
            # Update local tracking
            local_state['version'] = documents[doc_id]['version']
            local_state['last_hash'] = get_hash(textarea.value)
            
            status.text = '🟡 Typing...'
            
        except Exception as e:
            status.text = f'🔴 Error: {str(e)}'
    
    def on_blur():
        """When user stops typing (loses focus)"""
        local_state['is_typing'] = False
        status.text = '🟢 Connected'
    
    # Set typing flag to false after short delay
    async def reset_typing_flag():
        """Reset typing flag after 500ms of no input"""
        import asyncio
        await asyncio.sleep(0.5)
        local_state['is_typing'] = False
    
    def on_input():
        """Called on every keystroke"""
        on_change()
        ui.timer(0.5, reset_typing_flag, once=True)
    
    # Bind events
    textarea.on('update:model-value', on_input)
    textarea.on('blur', on_blur)
    
    # Check for updates from other users every 300ms
    ui.timer(0.3, check_for_updates)
    
    # Instructions
    with ui.expansion('How to use', icon='info').classes('mt-4 max-w-3xl'):
        ui.markdown('''
        **Testing collaborative editing:**
        1. Share this URL with your teammates
        2. Everyone opens the same document URL
        3. Start typing - changes appear almost instantly
        
        **How it works:**
        - Your changes save immediately as you type
        - Updates from others appear when you pause typing (500ms)
        - Last write wins (like Etherpad/simple collaborative editors)
        
        **Limitations:**
        - If two people type at the exact same time, last save wins
        - No cursor position syncing
        - Best for taking turns or working on different sections
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
                ui.label(doc_id).classes('font-mono')
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
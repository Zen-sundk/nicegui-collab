# nicegui_live_collab.py
from nicegui import ui
from datetime import datetime

# In-memory shared storage (works for single-process deployments)
documents = {}

@ui.page('/docs/{doc_id}')
def doc_room(doc_id: str):
    # Initialize document if it doesn't exist
    if doc_id not in documents:
        documents[doc_id] = {'text': '', 'last_updated': datetime.now()}
    
    ui.label(f'Document: {doc_id}').classes('text-2xl font-bold mb-4')
    
    # Create textarea
    textarea = ui.textarea(
        label='Live document (shared with all users)',
        placeholder='Start typing... Changes sync every 2 seconds'
    ).props('outlined autogrow').classes('w-full')
    
    # Set initial value
    textarea.value = documents[doc_id]['text']
    
    # Status indicators
    with ui.row().classes('gap-4 mt-2'):
        status = ui.label('Status: Connected').classes('text-green-600')
        last_sync = ui.label(f'Last sync: {datetime.now().strftime("%H:%M:%S")}')
        user_count = ui.label(f'Active users: {len(ui.context.client.instances)}')
    
    def sync_from_server():
        """Pull latest content from server"""
        try:
            if textarea.value != documents[doc_id]['text']:
                # Only update if content changed (avoid cursor jumps)
                cursor_pos = textarea.value  # Store for cursor management
                textarea.value = documents[doc_id]['text']
                last_sync.text = f'Last sync: {datetime.now().strftime("%H:%M:%S")}'
        except Exception as e:
            status.text = f'Status: Error - {str(e)}'
            status.classes(remove='text-green-600', add='text-red-600')
    
    def sync_to_server():
        """Push local content to server"""
        try:
            documents[doc_id]['text'] = textarea.value
            documents[doc_id]['last_updated'] = datetime.now()
            status.text = 'Status: Connected'
            status.classes(remove='text-red-600', add='text-green-600')
        except Exception as e:
            status.text = f'Status: Error - {str(e)}'
            status.classes(remove='text-green-600', add='text-red-600')
    
    def update_user_count():
        """Update active user count"""
        user_count.text = f'Active users: {len(ui.context.client.instances)}'
    
    # Sync changes TO server when user types
    textarea.on('update:model-value', sync_to_server)
    
    # Pull changes FROM server periodically (every 2 seconds)
    ui.timer(2.0, sync_from_server)
    
    # Update user count periodically
    ui.timer(3.0, update_user_count)
    
    # Instructions
    with ui.expansion('How to use', icon='info').classes('mt-4 max-w-3xl'):
        ui.markdown('''
        **Testing collaborative editing:**
        1. Share this URL with your teammates
        2. Everyone opens the same document URL
        3. Start typing - changes sync every 2 seconds
        4. You'll see the "Active users" counter update
        
        **Tips:**
        - Changes save automatically as you type
        - Refresh the page to see the latest content
        - Use different document IDs for different files (e.g., `/docs/meeting-notes`)
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
    ui.run(
        title='NiceGUI Live Collaboration',
        port=8080,
        reload=False,
        show=False
    )
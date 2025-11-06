# nicegui_live_collab.py
from nicegui import ui, app, context, events
import hashlib
import uuid
import time
import os
import asyncio
from datetime import datetime

# ============================================
# SHARED DATA (in-memory, lost on restart)
# ============================================
documents = {}      # {doc_id: {'text': str, 'version': int, 'created': datetime, 'modified': datetime}}
active_users = {}   # {doc_id: {user_id: timestamp}}

# ============================================
# HELPER FUNCTIONS
# ============================================
def get_hash(text):
    """Quick way to check if text changed"""
    return hashlib.md5(text.encode()).hexdigest()

def cleanup_inactive_users(doc_id):
    """Remove users who haven't been seen in 0.2 second"""
    if doc_id not in active_users:
        return 0
    current_time = time.time()
    active_users[doc_id] = {uid: ts for uid, ts in active_users[doc_id].items() 
                            if current_time - ts < 0.2}
    return len(active_users[doc_id])

def format_datetime(dt):
    """Format datetime til dansk format"""
    return dt.strftime('%d-%m-%Y %H:%M:%S')

# ============================================
# DOCUMENT PAGE (the main collaboration page)
# ============================================
@ui.page('/docs/{doc_id}')
async def doc_room(doc_id: str):
    user_id = str(uuid.uuid4())[:8]
    
    # Initialize document if new
    if doc_id not in documents:
        now = datetime.now()
        documents[doc_id] = {
            'text': '', 
            'version': 0,
            'created': now,
            'modified': now
        }
    if doc_id not in active_users:
        active_users[doc_id] = {}
    
    cleanup_inactive_users(doc_id)
    active_users[doc_id][user_id] = time.time()
    
    # ============================================
    # UI ELEMENTS - HEADER
    # ============================================
    with ui.row().classes('w-full justify-between items-center mb-4'):
        ui.label(f'📄 Document: {doc_id}').classes('text-2xl font-bold')
        ui.button('← Tilbage til oversigt', on_click=lambda: ui.navigate.to('/')).props('flat')
    
    # Document info
    doc_info = ui.label().classes('text-sm text-gray-600 mb-2')
    
    def update_doc_info():
        created = format_datetime(documents[doc_id]['created'])
        modified = format_datetime(documents[doc_id]['modified'])
        doc_info.set_text(f'Oprettet: {created} | Sidst ændret: {modified} | Version: {documents[doc_id]["version"]}')
    
    update_doc_info()
    
    # ============================================
    # TEXTAREA (skal defineres før upload handler)
    # ============================================
    textarea = ui.textarea('Live dokument (delt)', 
                          placeholder='Start typing...').props('outlined autogrow').classes('w-full')
    
    # ============================================
    # STATE TRACKING (skal defineres før upload handler)
    # ============================================
    state = {
        'version': documents[doc_id]['version'],
        'is_typing': False,
        'last_hash': get_hash(documents[doc_id]['text']),
        'pending_save': None,
        'local_text': documents[doc_id]['text'],
        'skip_next_save': False  # Flag til at springe save over efter upload
    }
    
    # Set initial value
    textarea.value = state['local_text']
    
    # ============================================
    # CORE FUNCTIONS (defineres før FILE OPERATIONS)
    # ============================================
    def update_word_count():
        """Opdater ordtælling"""
        text = textarea.value or ''
        words = len(text.split()) if text.strip() else 0
        chars = len(text)
        word_count.set_text(f'📝 Ord: {words} | Tegn: {chars}')
    
    def save():
        """Save current text to server"""
        # Skip hvis vi lige har uploaded
        if state['skip_next_save']:
            state['skip_next_save'] = False
            return
            
        documents[doc_id]['text'] = textarea.value
        documents[doc_id]['version'] += 1
        documents[doc_id]['modified'] = datetime.now()
        state['version'] = documents[doc_id]['version']
        state['last_hash'] = get_hash(textarea.value)
        state['local_text'] = textarea.value
        status.text = '🟢 Forbundet'
        update_doc_info()
        update_word_count()
        print(f"[{user_id}] SAVE - Doc: {doc_id}, Version: {documents[doc_id]['version']}, Length: {len(textarea.value)}")
    
    def sync():
        """Check for updates from others + update user count"""
        # Update this user's presence
        active_users[doc_id][user_id] = time.time()
        user_count.set_text(f'👥 Aktive brugere: {cleanup_inactive_users(doc_id)}')
        
        # Don't pull updates while typing
        if state['is_typing']:
            status.set_text('🟡 Skriver... (sync pause)')
            return
        
        # Pull updates if server has newer version
        server_version = documents[doc_id]['version']
        if server_version > state['version']:
            server_text = documents[doc_id]['text']
            
            # Only update if different from what we have locally
            if server_text != textarea.value:
                print(f"[{user_id}] SYNC PULLING - Local v{state['version']} → Server v{server_version}, Length: {len(server_text)}")
                
                # Opdater textarea direkte
                textarea.value = server_text
                
                state['version'] = server_version
                state['last_hash'] = get_hash(server_text)
                state['local_text'] = server_text
                state['skip_next_save'] = True  # Skip næste save
                status.set_text('🟢 Synkroniseret fra server')
                update_doc_info()
                update_word_count()
    
    def on_type():
        """Called every time user types a character"""
        state['is_typing'] = True
        state['local_text'] = textarea.value
        status.set_text('🟡 Skriver...')
        update_word_count()
        
        # Cancel previous save timer
        if state['pending_save']:
            state['pending_save'].deactivate()
        
        # Save 200ms after user stops typing
        def finish_typing():
            save()
            state['is_typing'] = False
        
        state['pending_save'] = ui.timer(0.2, finish_typing, once=True)
    
    def on_blur():
        """When textarea loses focus, save immediately"""
        if state['pending_save']:
            state['pending_save'].deactivate()
        save()
        state['is_typing'] = False
    
    # ============================================
    # FILE OPERATIONS ROW
    # ============================================
    with ui.row().classes('gap-2 mb-4 w-full'):
        # Upload knap - KORRIGERET VERSION (NiceGUI 3.x kompatibel)
        async def handle_upload(e: events.UploadEventArguments):
            """Håndter fil upload - Async og korrekt brug af e.file"""
            try:
                print(f"[{user_id}] UPLOAD EVENT - File: {e.file.name}, Type: {e.file.content_type}")

                # Læs filens indhold som tekst (NiceGUI håndterer encoding automatisk)
                text = await e.file.text()

                print(f"[{user_id}] UPLOAD START - Length: {len(text)}, File: {e.file.name}")

                # 1. Annuller eventuel pending save FØRST
                if state['pending_save']:
                    state['pending_save'].deactivate()
                    state['pending_save'] = None

                # 2. Gem til server
                documents[doc_id]['text'] = text
                documents[doc_id]['version'] += 1
                documents[doc_id]['modified'] = datetime.now()

                print(f"[{user_id}] UPLOAD - Saved to server. Version: {documents[doc_id]['version']}")

                # 3. Opdater textarea direkte
                textarea.value = text

                # 4. Opdater lokal state
                state['version'] = documents[doc_id]['version']
                state['last_hash'] = get_hash(text)
                state['local_text'] = text
                state['is_typing'] = False
                state['skip_next_save'] = True

                # 5. Opdater UI
                update_doc_info()
                update_word_count()
                status.set_text(f'✅ Fil uploadet: {e.file.name}')

                print(f"[{user_id}] UPLOAD COMPLETE - Doc: {doc_id}, Version: {documents[doc_id]['version']}")

            except Exception as ex:
                print(f"[{user_id}] UPLOAD ERROR: {ex}")
                import traceback
                traceback.print_exc()
                status.set_text('❌ Upload fejlede')

        upload = ui.upload(
            label='📁 Upload fil',
            on_upload=handle_upload,
            auto_upload=True,
        ).props('accept=".txt,.md,.html,.py,.js,.json,.xml,.csv"').classes('max-w-xs')

        # Download knap
        def download_doc():
            """Download dokument som fil"""
            try:
                content = textarea.value or ''
                filename = f'{doc_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                ui.download(content=content.encode('utf-8'), filename=filename)
                ui.notify(f'💾 Downloader: {filename}', color='positive')
            except Exception as ex:
                ui.notify(f'❌ Fejl ved download: {str(ex)}', color='negative')

        ui.button('💾 Download', on_click=download_doc).props('outlined')

        # Nyt dokument knap (clear)
        def clear_doc():
            """Ryd dokument"""
            if state['pending_save']:
                state['pending_save'].deactivate()
                state['pending_save'] = None

            # Ryd dokument og opdater version
            documents[doc_id]['text'] = ''
            documents[doc_id]['version'] += 1
            documents[doc_id]['modified'] = datetime.now()

            textarea.value = ''
            state['version'] = documents[doc_id]['version']
            state['last_hash'] = get_hash('')
            state['local_text'] = ''
            state['is_typing'] = False
            state['skip_next_save'] = True

            update_doc_info()
            update_word_count()
            ui.notify('🗑️ Dokument ryddet', color='warning')
            print(f"[{user_id}] CLEAR - Doc: {doc_id}, Version: {documents[doc_id]['version']}")

        ui.button('🗑️ Ryd alt', on_click=clear_doc).props('flat color=negative')

    # ============================================
    # STATUS ROW
    # ============================================
    with ui.row().classes('gap-4 mt-2'):
        status = ui.label('🟢 Forbundet').classes('text-sm')
        user_count = ui.label('👥 Aktive brugere: 1').classes('text-sm')
        word_count = ui.label('📝 Ord: 0').classes('text-sm text-gray-600')
    
    # ============================================
    # EVENT BINDINGS
    # ============================================
    textarea.on('update:model-value', on_type)
    textarea.on('blur', on_blur)
    
    # Check for updates every 150ms
    ui.timer(0.15, sync)
    
    # Initial word count
    update_word_count()

# ============================================
# HOME PAGE
# ============================================
@ui.page('/')
def index():
    ui.label('📝 NiceGUI Collaborative Document Editor').classes('text-3xl font-bold mb-4')
    ui.markdown('### 🚀 Hurtig Start\nIntast et dokumentnavn for at oprette eller åbne:')
    
    doc_input = ui.input('Dokumentnavn', placeholder='f.eks. mødereferat').classes('w-full max-w-md').props('outlined')
    
    def open_doc():
        name = ''.join(c for c in (doc_input.value.strip() or 'default') if c.isalnum() or c in '-_')
        ui.navigate.to(f'/docs/{name}')
    
    with ui.row().classes('gap-2'):
        ui.button('📂 Åbn Dokument', on_click=open_doc).classes('mt-2')
        ui.button('🔄 Opdater', on_click=lambda: ui.navigate.reload()).props('flat').classes('mt-2')
    
    doc_input.on('keydown.enter', open_doc)
    
    # Show existing documents
    if documents:
        ui.label('📚 Eksisterende dokumenter:').classes('text-xl font-bold mt-8 mb-2')
        
        # Sort by modified date (newest first)
        sorted_docs = sorted(
            documents.items(), 
            key=lambda x: x[1]['modified'], 
            reverse=True
        )
        
        for doc_id, doc_data in sorted_docs:
            with ui.card().classes('w-full max-w-md'):
                with ui.row().classes('w-full justify-between items-center'):
                    ui.label(doc_id).classes('font-mono font-bold')
                    count = cleanup_inactive_users(doc_id)
                    if count > 0:
                        ui.label(f'👥 {count}').classes('text-sm text-green-600 font-bold')
                
                # Document stats
                word_count = len(doc_data['text'].split()) if doc_data['text'].strip() else 0
                modified = format_datetime(doc_data['modified'])
                ui.label(f'📝 {word_count} ord | 🕒 Ændret: {modified}').classes('text-xs text-gray-500 mt-1')
                
                # Preview
                preview = doc_data['text'][:100] + ('...' if len(doc_data['text']) > 100 else '')
                ui.label(preview or '(tomt dokument)').classes('text-gray-600 text-sm mt-2')
                
                # Actions
                with ui.row().classes('gap-2 mt-2'):
                    ui.button('📂 Åbn', on_click=lambda d=doc_id: ui.navigate.to(f'/docs/{d}')).props('flat color=primary')
                    
                    def download_from_home(doc_id=doc_id):
                        content = documents[doc_id]['text']
                        filename = f'{doc_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                        ui.download(content=content.encode('utf-8'), filename=filename)
                        ui.notify(f'💾 Downloader: {filename}')
                    
                    ui.button('💾 Download', on_click=download_from_home).props('flat')
    else:
        ui.label('Ingen dokumenter endnu. Opret dit første dokument ovenfor! 👆').classes('text-gray-500 italic mt-4')

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
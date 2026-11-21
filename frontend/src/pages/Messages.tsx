import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';

type Item = { patient_id: number | null; name: string; phone: string; whatsapp_url: string | null; status: string };
type SavedContact = { id: number; name: string; phone: string; list_kind?: string };

const GREETING = 'Warm wishes from {clinic}. We hope you are keeping well.';

export default function Messages() {
  const [kind, setKind] = useState<'greeting' | 'message' | 'video'>('greeting');
  const [message, setMessage] = useState(GREETING);
  const [videoTitle, setVideoTitle] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [videoToken, setVideoToken] = useState('');
  const [videoName, setVideoName] = useState('');
  const [contacts, setContacts] = useState<SavedContact[]>([]);
  const [contactName, setContactName] = useState('');
  const [contactPhone, setContactPhone] = useState('');
  const [testName, setTestName] = useState('');
  const [testPhone, setTestPhone] = useState('');
  const [uploading, setUploading] = useState(false);
  const [items, setItems] = useState<Item[]>([]);
  const [summary, setSummary] = useState('');
  const [twilio, setTwilio] = useState(false);
  const [cursor, setCursor] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.remindersStatus().then(row => setTwilio(Boolean(row.auto_send_available))).catch(() => {});
    api.messageContacts().then(setContacts).catch(() => {});
  }, []);

  const savedContacts = contacts.filter(row => (row.list_kind || 'saved') !== 'test');
  const testContacts = contacts.filter(row => row.list_kind === 'test');

  const addContact = async (listKind: 'saved' | 'test') => {
    const name = (listKind === 'test' ? testName : contactName).trim();
    const phone = (listKind === 'test' ? testPhone : contactPhone).trim();
    setError('');
    try {
      const saved = await api.saveMessageContact({ name, phone, list_kind: listKind });
      setContacts(current => [...current.filter(row => row.id !== saved.id && row.phone !== saved.phone), saved].sort((a, b) => a.name.localeCompare(b.name)));
      if (listKind === 'test') {
        setTestName('');
        setTestPhone('');
      } else {
        setContactName('');
        setContactPhone('');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save this number');
    }
  };

  const removeContact = async (id: number) => {
    setError('');
    try {
      await api.deleteMessageContact(id);
      setContacts(current => current.filter(row => row.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not remove this number');
    }
  };

  const preview = useMemo(() => {
    const name = 'the patient';
    if (kind === 'video' && videoToken) {
      return `The video file is sent in the WhatsApp chat.\nNamaste ${name},${videoTitle.trim() ? `\n${videoTitle.trim()}` : ''}${message.trim() ? `\n${message.trim()}` : ''}`;
    }
    if (kind === 'video') {
      const title = videoTitle.trim() ? `: ${videoTitle.trim()}` : '';
      return `Namaste ${name},\nThe clinic has shared a short video${title}\n${videoUrl.trim() || 'https://'}${message.trim() ? `\n${message.trim()}` : ''}`;
    }
    const body = (message.trim() || GREETING).replace('{name}', name).replace('{clinic}', 'the clinic');
    return body.toLowerCase().includes(name) ? body : `Namaste ${name},\n${body}`;
  }, [kind, message, videoTitle, videoUrl, videoToken]);

  const prepare = async (deliver: boolean) => {
    setLoading(true);
    setError('');
    try {
      const result = await api.broadcastMessage({
        kind,
        message: message.trim(),
        video_title: videoTitle.trim(),
        video_url: videoUrl.trim(),
        deliver,
      });
      setItems(result.items);
      setTwilio(result.twilio);
      setCursor(0);
      const sent = deliver && result.twilio
        ? `Sent ${result.delivered}. Failed ${result.failed}.`
        : 'WhatsApp chats are ready. Open the next chat, press send there, then come back for the next patient.';
      setSummary(`${result.audience} patients with a mobile number. ${result.skipped_without_phone} charts have no mobile. ${sent}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not prepare the messages');
    } finally {
      setLoading(false);
    }
  };

  const openNext = () => {
    const item = items[cursor];
    if (!item?.whatsapp_url) return;
    window.open(item.whatsapp_url, '_blank', 'noopener,noreferrer');
    setCursor(current => current + 1);
  };

  const uploadVideo = async (file: File | null) => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      const saved = await api.uploadEducationVideo(file, videoTitle.trim() || file.name.replace(/\.[^.]+$/, ''));
      setVideoUrl(saved.url);
      setVideoToken(saved.token);
      setVideoTitle(saved.title);
      setVideoName(file.name);
      if (!message.trim()) setMessage('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not upload the video');
    } finally {
      setUploading(false);
    }
  };

  const sendAll = async (audience: 'patients' | 'test' = 'patients') => {
    if (kind === 'video' && !videoToken && !videoUrl.trim()) {
      setError('Upload a video or paste a video link first.');
      return;
    }
    if (audience === 'test' && testContacts.length === 0) {
      setError('Add a private number to the test list first.');
      return;
    }
    const fileSend = kind === 'video' && Boolean(videoToken);
    const who = audience === 'test'
      ? `only the ${testContacts.length} private number${testContacts.length === 1 ? '' : 's'} on the test list. Registered patients are not included.`
      : 'every registered patient with a mobile, and every extra saved number. The test list is not included.';
    const prompt = `Send this to ${who} One click sends every chat. Leave WhatsApp in front until it finishes.`;
    if (!window.confirm(prompt)) return;
    setLoading(true);
    setError('');
    try {
      const result = await api.broadcastMessage({
        kind,
        message: message.trim(),
        video_title: videoTitle.trim(),
        video_url: videoUrl.trim(),
        deliver: twilio && !fileSend,
        as_file: fileSend,
        audience,
      });
      setItems(result.items);
      setTwilio(result.twilio);
      setCursor(0);
      if (result.audience === 0) {
        setSummary(audience === 'test'
          ? 'The test list has no numbers yet.'
          : `No mobile numbers to message. ${result.skipped_without_phone} charts have no mobile.`);
        return;
      }
      if (fileSend) {
        let sent = 0;
        for (const item of result.items) {
          setSummary(`Sending the video to ${item.name} (${sent + 1} of ${result.items.length}). Keep WhatsApp in front.`);
          await api.sendWhatsAppVideo({
            phone: item.phone,
            name: item.name,
            token: videoToken,
            message: message.trim(),
            video_title: videoTitle.trim(),
          });
          sent += 1;
          setCursor(sent);
        }
        setSummary(audience === 'test'
          ? `Sent the video file to ${sent} numbers on the test list.`
          : `Sent the video file to ${sent} chats. ${result.skipped_without_phone} charts have no mobile.`);
        return;
      }
      if (twilio) {
        setSummary(audience === 'test'
          ? `Sent ${result.delivered} of ${result.audience} on the test list. Failed ${result.failed}.`
          : `Sent ${result.delivered} of ${result.audience}. Failed ${result.failed}. ${result.skipped_without_phone} charts have no mobile.`);
        setCursor(result.items.length);
        return;
      }
      let sentText = 0;
      for (const item of result.items) {
        setSummary(`Sending to ${item.name} (${sentText + 1} of ${result.items.length}). Keep WhatsApp in front.`);
        await api.sendWhatsAppText({
          phone: item.phone,
          name: item.name,
          kind,
          message: message.trim(),
          video_title: videoTitle.trim(),
          video_url: videoUrl.trim(),
        });
        sentText += 1;
        setCursor(sentText);
      }
      setItems(result.items.map(item => ({ ...item, status: 'sent' })));
      setSummary(audience === 'test'
        ? `Sent to ${sentText} numbers on the test list.`
        : `Sent to ${sentText} chats. ${result.skipped_without_phone} charts have no mobile.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send the messages');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2>Patient messages</h2>
          <p className="page-subtitle">Try a message on your private test list first. Send to all patients only when that looks right.</p>
        </div>
      </div>
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="card p-4 mb-4">
        <h5 className="mb-1">Test list</h5>
        <p className="text-muted small">Add your own private numbers here. Send to test list uses only these numbers. Registered patient mobiles are not used.</p>
        <div className="row g-2 mb-3">
          <div className="col-md-5">
            <input className="form-control" placeholder="Name" value={testName} onChange={e => setTestName(e.target.value)} />
          </div>
          <div className="col-md-4">
            <input className="form-control" placeholder="10-digit mobile" inputMode="numeric" maxLength={10} value={testPhone} onChange={e => setTestPhone(e.target.value.replace(/\D/g, '').slice(0, 10))} />
          </div>
          <div className="col-md-3">
            <button type="button" className="btn btn-outline-primary w-100" onClick={() => addContact('test')}>Add to test list</button>
          </div>
        </div>
        {testContacts.length === 0 ? <div className="text-muted small">No private numbers on the test list yet.</div> : (
          <ul className="mb-0">
            {testContacts.map(contact => (
              <li key={contact.id} className="d-flex justify-content-between align-items-center">
                <span>{contact.name} · {contact.phone}</span>
                <button type="button" className="btn btn-sm btn-link text-danger" onClick={() => removeContact(contact.id)}>Remove</button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="card p-4 mb-4">
        <h5 className="mb-1">Other numbers</h5>
        <p className="text-muted small">Save a name and mobile that is not on the patient register. These stay here for the next message.</p>
        <div className="row g-2 mb-3">
          <div className="col-md-5">
            <input className="form-control" placeholder="Name" value={contactName} onChange={e => setContactName(e.target.value)} />
          </div>
          <div className="col-md-4">
            <input className="form-control" placeholder="10-digit mobile" inputMode="numeric" maxLength={10} value={contactPhone} onChange={e => setContactPhone(e.target.value.replace(/\D/g, '').slice(0, 10))} />
          </div>
          <div className="col-md-3">
            <button type="button" className="btn btn-outline-primary w-100" onClick={() => addContact('saved')}>Save number</button>
          </div>
        </div>
        {savedContacts.length === 0 ? <div className="text-muted small">No extra numbers saved yet.</div> : (
          <ul className="mb-0">
            {savedContacts.map(contact => (
              <li key={contact.id} className="d-flex justify-content-between align-items-center">
                <span>{contact.name} · {contact.phone}</span>
                <button type="button" className="btn btn-sm btn-link text-danger" onClick={() => removeContact(contact.id)}>Remove</button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="card p-4 mb-4">
        <div className="btn-group mb-3">
          {([
            ['greeting', 'Greeting'],
            ['message', 'Message'],
            ['video', 'Education video'],
          ] as const).map(([id, label]) => (
            <button key={id} type="button" className={`btn ${kind === id ? 'btn-primary' : 'btn-outline-primary'}`} onClick={() => setKind(id)}>{label}</button>
          ))}
        </div>
        {kind === 'video' && (
          <div className="row g-2 mb-3">
            <div className="col-md-4">
              <label className="form-label">Video title</label>
              <input className="form-control" value={videoTitle} onChange={e => setVideoTitle(e.target.value)} placeholder="Understanding HbA1c" />
            </div>
            <div className="col-md-8">
              <label className="form-label">Video link</label>
              <input className="form-control" value={videoUrl} onChange={e => { setVideoUrl(e.target.value); setVideoName(''); setVideoToken(''); }} placeholder="https://youtu.be/..." />
            </div>
            <div className="col-12">
              <label className="form-label">Or upload a video</label>
              <input
                className="form-control"
                type="file"
                accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov,.m4v"
                disabled={uploading}
                onChange={e => { uploadVideo(e.target.files?.[0] || null); e.target.value = ''; }}
              />
              <div className="form-text">
                {uploading ? 'Uploading…' : videoName ? `Uploaded ${videoName}. Send to all places this video in each WhatsApp chat.` : 'mp4, webm, or mov, up to 80 MB. An uploaded file is sent as the video. A pasted link is only a link.'}
              </div>
              {videoUrl && videoName && <video className="mt-2 w-100" style={{ maxHeight: 240 }} controls src={videoUrl} />}
            </div>
          </div>
        )}
        <label className="form-label">{kind === 'video' ? 'Extra line, optional' : 'Message'}</label>
        <textarea className="form-control mb-2" rows={4} value={message} onChange={e => setMessage(e.target.value)} />
        <div className="small text-muted mb-3">Use {'{name}'} and {'{clinic}'} where you want the person’s name and the clinic name. One click sends every chat on the list you choose. Leave WhatsApp in front until it finishes. The message does not include the chart or the diagnosis.</div>
        <div className="border rounded p-3 bg-light small mb-3" style={{ whiteSpace: 'pre-wrap' }}>{preview}</div>
        <div className="d-flex flex-wrap gap-2">
          <button type="button" className="btn btn-success" disabled={loading || uploading || testContacts.length === 0} onClick={() => sendAll('test')}>
            <i className="fab fa-whatsapp me-1"></i>{loading ? 'Sending…' : 'Send to test list'}
          </button>
          <button type="button" className="btn btn-outline-success" disabled={loading || uploading} onClick={() => sendAll('patients')}>
            <i className="fab fa-whatsapp me-1"></i>{loading ? 'Sending…' : 'Send to all patients'}
          </button>
          <button type="button" className="btn btn-outline-primary" disabled={loading || uploading} onClick={() => prepare(false)}>
            {loading ? 'Preparing…' : 'Prepare list'}
          </button>
        </div>
      </div>
      {summary && <div className="alert alert-info">{summary}</div>}
      {items.length > 0 && items.some(item => item.status !== 'sent') && (
        <div className="card p-4">
          <div className="d-flex justify-content-between align-items-center mb-3">
            <div>
              <h5 className="mb-0">Send one chat at a time</h5>
              <div className="small text-muted">{Math.min(cursor, items.length)} of {items.length} opened</div>
            </div>
            <button type="button" className="btn btn-success" disabled={cursor >= items.length} onClick={openNext}>
              <i className="fab fa-whatsapp me-1"></i>
              {cursor >= items.length ? 'All chats opened' : `Open ${items[cursor]?.name || 'next'}`}
            </button>
          </div>
          <ul className="mb-0">
            {items.slice(0, 12).map((item, index) => (
              <li key={`${item.phone}-${index}`} className={index < cursor ? 'text-muted' : ''}>
                {item.name} · {item.phone}{index < cursor ? ' · opened' : ''}
              </li>
            ))}
            {items.length > 12 && <li className="text-muted">and {items.length - 12} more</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

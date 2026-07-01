'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { apiClient } from '@/lib/api-client';

export default function NewFlowPage() {
  const t = useTranslations('flows');
  const router = useRouter();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [triggerType, setTriggerType] = useState<'first_contact' | 'keyword' | 'action_result' | 'schedule'>('first_contact');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await apiClient.post('/flows', {
        name,
        description: description || null,
        trigger_type: triggerType,
        trigger_config: {}, // empty for now
        nodes: [],
        edges: [],
      });
      router.push('/flows');
    } catch (err: any) {
      console.error(err);
      const msg = err.response?.data?.detail ?? 'Failed to create flow';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className='p-8 max-w-2xl mx-auto'>
      <div className='mb-6'>
        <h1 className='text-2xl font-semibold'>{t('create')}</h1>
        <p className='text-muted-foreground text-sm mt-1'>{t('create_flow_desc')}</p>
      </div>

      {error && (
        <div className='mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-600'>
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className='space-y-4'>
        <div>
          <label className='block text-sm font-medium text-foreground mb-2'>{t('name')}</label>
          <input
            type='text'
            value={name}
            onChange={(e) => setName(e.target.value)}
            className='w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
            placeholder={t('flow_name_placeholder')}
            required
          />
        </div>

        <div>
          <label className='block text-sm font-medium text-foreground mb-2'>{t('description')}</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className='w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
            placeholder={t('flow_description_placeholder')}
            rows={4}
          />
        </div>

        <div>
          <label className='block text-sm font-medium text-foreground mb-2'>{t('trigger_type')}</label>
          <select
            value={triggerType}
            onChange={(e) => setTriggerType(e.target.value as any)}
            className='w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary'
          >
            <option value='first_contact'>{t('trigger.first_contact')}</option>
            <option value='keyword'>{t('trigger.keyword')}</option>
            <option value='action_result'>{t('trigger.action_result')}</option>
            <option value='schedule'>{t('trigger.schedule')}</option>
          </select>
        </div>

        <div className='mt-6'>
          <label className='block text-sm font-medium text-foreground mb-2'>{t('flow_builder_placeholder')}</label>
          <div className='min-h-[300px] bg-gray-50 border border-gray-200 rounded-md flex items-center justify-center text-gray-400'>
            Flow builder canvas will be integrated here (React Flow / @xyflow)
          </div>
        </div>

        <div className='flex justify-end space-x-3'>
          <button
            type='button'
            onClick={() => router.push('/flows')}
            className='px-4 py-2 border border-gray-300 rounded-md text-sm font-medium hover:bg-gray-50'
          >
            {t('cancel')}
          </button>
          <button
            type='submit'
            disabled={loading}
            className={`px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50`}
          >
            {loading ? t('creating') : t('create')}
          </button>
        </div>
      </form>
    </div>
  );
}
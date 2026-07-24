import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

serve(async (req) => {
  // 1. รองรับ CORS สำหรับยิงจาก Vercel Frontend หรือ Roblox Studio
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
      }
    })
  }

  try {
    const { prompt, user_id } = await req.json()

    // 2. ดึงค่า Environment Variables จาก Supabase ถาวร
    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // 3. บันทึกข้อมูลลงตาราง prompts
    const { data, error } = await supabase
      .from('prompts')
      .insert([{ user_id, content: prompt }])

    if (error) throw error

    // 4. ส่งคำตอบกลับไปหา Frontend
    return new Response(
      JSON.stringify({ 
        status: "success", 
        message: "Prompt saved to Supabase successfully!",
        data: data 
      }),
      { 
        headers: { 
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*" 
        } 
      }
    )
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err.message }), 
      { status: 400, headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" } }
    )
  }
})
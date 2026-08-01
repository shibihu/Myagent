import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

serve(async (req) => {
  // 1. รองรับ CORS สำหรับยิงจาก Vercel
  if (req.method === 'OPTIONS') {
    return new Response('ok', {
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
      }
    })
  }

  // 2. ตอบกลับเมื่อเปิดดูผ่าน Browser หน้าตรง (GET)
  if (req.method === 'GET') {
    return new Response(
      JSON.stringify({ message: "MyAgent API is ready!" }),
      { headers: { "Content-Type": "application/json" } }
    )
  }

  try {
    // 3. อ่าน Token จาก Header ที่ส่งมาจาก Frontend
    const authHeader = req.headers.get('Authorization')
    if (!authHeader) throw new Error("Missing Authorization Header")

    const supabaseUrl = Deno.env.get('SUPABASE_URL') ?? ''
    const supabaseServiceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
    
    // สร้าง Supabase Client
    const supabase = createClient(supabaseUrl, supabaseServiceKey)

    // 4. ตรวจสอบ User ที่ล็อกอินผ่าน GitHub Token
    const token = authHeader.replace('Bearer ', '')
    const { data: { user }, error: userError } = await supabase.auth.getUser(token)

    if (userError || !user) {
      throw new Error("Unauthorized: กรุณาเข้าสู่ระบบด้วย GitHub ก่อน")
    }

    // 5. อ่านข้อความ prompt จาก Body
    const { prompt } = await req.json()
    if (!prompt) throw new Error("Prompt is required")

    // 6. บันทึกข้อมูลลง Database พร้อม user_id ของคนที่ล็อกอิน
    const { data, error } = await supabase
      .from('prompts')
      .insert([{ user_id: user.id, content: prompt }])
      .select()

    if (error) throw error

    return new Response(
      JSON.stringify({ 
        status: "success", 
        message: "บันทึกข้อมูลสำเร็จ!",
        user: { id: user.id, email: user.email },
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
      { 
        status: 400, 
        headers: { 
          "Content-Type": "application/json", 
          "Access-Control-Allow-Origin": "*" 
        } 
      }
    )
  }
})
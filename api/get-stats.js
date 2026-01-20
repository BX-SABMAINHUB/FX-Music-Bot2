const { MongoClient } = require('mongodb');

// Tu link de conexión real
const uri = "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority";

export default async function handler(req, res) {
    const client = new MongoClient(uri);
    try {
        await client.connect();
        const db = client.db("flexus_data");
        // Buscamos el registro que el bot actualiza
        const stats = await db.collection("ads_stats").findOne({ id: "global" });
        
        // Enviamos el número de vistas a la web
        res.status(200).json({ views: stats ? stats.views : 0 });
    } catch (e) {
        res.status(500).json({ error: e.message });
    } finally {
        await client.close();
    }
}

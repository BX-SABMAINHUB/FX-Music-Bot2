const { MongoClient } = require('mongodb');

// Usamos la URL de tu clúster de MongoDB
const uri = process.env.MONGODB_URI || "mongodb+srv://Alexgaming:Alex27Junio@cluster0.55a5siw.mongodb.net/?retryWrites=true&w=majority";

// Configuramos el cliente para que sea eficiente
const client = new MongoClient(uri, {
  useNewUrlParser: true,
  useUnifiedTopology: true,
});

export default async function handler(req, res) {
  // Habilitar CORS para que la web pueda consultar la API sin bloqueos
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');

  try {
    await client.connect();
    const db = client.db('flexus_data');
    const reviewsCol = db.collection('reviews');

    // Obtenemos las últimas 12 reseñas, ordenadas por la más reciente
    const reviews = await reviewsCol
      .find({})
      .sort({ timestamp: -1 })
      .limit(12)
      .toArray();

    // Enviamos los datos con éxito
    return res.status(200).json(reviews);

  } catch (error) {
    console.error("❌ Error en la API de Flexus:", error);
    
    // Si algo falla, enviamos un array vacío para que la web no se rompa
    return res.status(500).json([]);
    
  } finally {
    // Cerramos la conexión para no saturar MongoDB
    await client.close();
  }
}

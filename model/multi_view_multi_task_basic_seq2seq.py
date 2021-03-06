from model.rnn_encoder import *
from model.multi_task_basic_decoder import MultiTaskBasicDecoder
from utils import io
from model.word_attn_classifier import WordAttnClassifier
from model.pooling_classifier import MaxPoolClassifier
from model.word_attn_no_query_classifier import WordAttnNoQueryClassifier
from model.word_multi_hop_attn_classifier import WordMultiHopAttnClassifier
from torch.nn import init
class MultiViewMultiTaskBasicClassifySeq2Seq(nn.Module):
    """Container module with an encoder, decoder, embeddings."""
    def __init__(self, opt, rating_tokens_tensor=None):
        """Initialize model :param rating_tokens_tensor: a LongTensor, [5, rating_v_size], stores the top rating_v_size tokens' indexs of each rating score """
        super(MultiViewMultiTaskBasicClassifySeq2Seq, self).__init__()
        self.vocab_size = len(opt.word2idx)
        self.emb_dim = opt.word_vec_size
        self.num_directions = 2 if opt.bidirectional else 1
        self.encoder_size = opt.encoder_size
        self.decoder_size = opt.decoder_size
        
        self.memory_bank_size = self.num_directions * self.encoder_size
        #self.ctx_hidden_dim = opt.rnn_size
        self.batch_size = opt.batch_size
        self.bidirectional = opt.bidirectional
        self.enc_layers = opt.enc_layers
        self.dec_layers = opt.dec_layers
        self.dropout = opt.dropout
        self.model_type = opt.model_type
        self.bridge = opt.bridge
        self.coverage_attn = opt.coverage_attn
        self.copy_attn = opt.copy_attention
        # for rating memory
        self.rating_memory_pred = opt.rating_memory_pred
        self.rating_memory_type = opt.rating_memory_type
        self.rating_bridge_type = opt.rating_bridge_type
        if self.rating_memory_pred:
            assert rating_tokens_tensor is not None, "The rating_tokens_tensor is needed when rating_memory_pred is True"
            self.rating_tokens_tensor = rating_tokens_tensor.cuda()
            if self.rating_bridge_type == 'relu_one_layer':
                self.rating_bridge = nn.Sequential(nn.Linear(self.emb_dim, self.emb_dim),
                                                   nn.Dropout(p=self.dropout),
                                                   nn.ReLU())
            elif self.rating_bridge_type == 'tanh_one_layer':
                self.rating_bridge = nn.Sequential(nn.Linear(self.emb_dim, self.emb_dim),
                                                   nn.Dropout(p=self.dropout),
                                                   nn.Tanh())
            else:
                self.rating_bridge = None
        else:
            self.rating_tokens_tensor = None
            self.rating_bridge = None
        self.pad_idx_src = io.PAD
        self.pad_idx_trg = io.PAD
        self.bos_idx = io.BOS
        self.eos_idx = io.EOS
        self.unk_idx = io.UNK
        self.sep_idx = None
        # self.sep_idx = opt.word2idx['.']
        self.orthogonal_loss = opt.orthogonal_loss
        if self.orthogonal_loss:
            assert self.sep_idx is not None
        self.share_embeddings = opt.share_embeddings
        self.review_attn = opt.review_attn
        self.attn_mode = opt.attn_mode
        self.hr_enc = opt.encoder_type == "hre_brnn"
        if opt.encoder_type == 'sep_layers_brnn':
            self.separate_mode = 1
            self.separate_layer_enc = True
        elif opt.encoder_type == 'sep_layers_brnn_reverse':
            self.separate_mode = 2
            self.separate_layer_enc = True
        elif opt.encoder_type == 'rnn' and opt.enc_layers == 2 and opt.residual:
            self.separate_mode = 0
            self.separate_layer_enc = False
        elif opt.residual and opt.enc_layers != 2:
            raise ValueError
        else:
            self.separate_mode = -1
            self.separate_layer_enc = False
        self.num_classes = opt.num_classes
        self.classifier_type = opt.classifier_type
        self.dec_classify_input_type = opt.dec_classify_input_type
        self.detach_classify_dec_states = opt.detach_classify_dec_states
        if self.detach_classify_dec_states:
            assert opt.dec_classify_input_type == "dec_state"
        if opt.classifier_type == "word_attn":
            self.enc_classifier = WordAttnClassifier(opt.query_hidden_size, self.memory_bank_size, opt.num_classes, opt.attn_mode, opt.classifier_dropout, opt.ordinal, self.hr_enc)
            # self.dec_classifier = WordAttnClassifier(opt.query_hidden_size, self.memory_bank_size, opt.num_classes, opt.attn_mode, opt.classifier_dropout, opt.ordinal)
        elif opt.classifier_type == "max":
            self.enc_classifier = MaxPoolClassifier(self.memory_bank_size, opt.num_classes, opt.classifier_dropout, opt.ordinal, self.hr_enc)
            # self.dec_classifier = MaxPoolClassifier(self.memory_bank_size, opt.num_classes, opt.classifier_dropout, opt.ordinal)
        elif opt.classifier_type == "word_attn_no_query":
            self.enc_classifier = WordAttnNoQueryClassifier(self.memory_bank_size, opt.num_classes, opt.classifier_dropout, opt.ordinal, self.hr_enc)
            # self.dec_classifier = WordAttnNoQueryClassifier(self.memory_bank_size, opt.num_classes, opt.classifier_dropout, opt.ordinal)
        elif opt.classifier_type == "word_multi_hop_attn":
            self.enc_classifier = WordMultiHopAttnClassifier(opt.query_hidden_size, self.memory_bank_size, opt.num_classes, opt.attn_mode, opt.classifier_dropout, opt.ordinal, self.hr_enc)
            # self.dec_classifier = WordMultiHopAttnClassifier(opt.query_hidden_size, self.memory_bank_size, opt.num_classes, opt.attn_mode, opt.classifier_dropout, opt.ordinal)
        else:
            raise ValueError
        if opt.dec_classifier_type == "word_attn":
            self.dec_classifier = WordAttnClassifier(opt.query_hidden_size, self.memory_bank_size, opt.num_classes, opt.attn_mode, opt.classifier_dropout, opt.ordinal)
        elif opt.dec_classifier_type == "max":
            self.dec_classifier = MaxPoolClassifier(self.memory_bank_size, opt.num_classes, opt.classifier_dropout, opt.ordinal)
        elif opt.dec_classifier_type == "word_attn_no_query":
            self.dec_classifier = WordAttnNoQueryClassifier(self.memory_bank_size, opt.num_classes, opt.classifier_dropout, opt.ordinal)
        elif opt.dec_classifier_type == "word_multi_hop_attn":
            self.dec_classifier = WordMultiHopAttnClassifier(opt.query_hidden_size, self.memory_bank_size, opt.num_classes, opt.attn_mode, opt.classifier_dropout, opt.ordinal)
        else:
            raise ValueError
        #self.goal_vector_mode = opt.goal_vector_mode
        #self.goal_vector_size = opt.goal_vector_size
        #self.manager_mode = opt.manager_mode
        if self.hr_enc:
            assert not self.separate_layer_enc
            assert not self.separate_layer_enc_reverse
            self.encoder = CatHirRNNEncoder(
                vocab_size=self.vocab_size,
                embed_size=self.emb_dim,
                hidden_size=self.encoder_size,
                num_layers=self.enc_layers,
                bidirectional=self.bidirectional,
                pad_token=self.pad_idx_src,
                dropout=self.dropout
            )
        elif self.separate_mode >= 0:
            self.encoder = TwoLayerRNNEncoder(
                vocab_size=self.vocab_size,
                embed_size=self.emb_dim,
                hidden_size=self.encoder_size,
                num_layers=self.enc_layers,
                bidirectional=self.bidirectional,
                pad_token=self.pad_idx_src,
                dropout=self.dropout,
                separate_mode=self.separate_mode,
                residual=opt.residual
            )
        else:
            self.encoder = RNNEncoderBasic(
                vocab_size=self.vocab_size,
                embed_size=self.emb_dim,
                hidden_size=self.encoder_size,
                num_layers=self.enc_layers,
                bidirectional=self.bidirectional,
                pad_token=self.pad_idx_src,
                dropout=self.dropout
            )

        self.decoder = MultiTaskBasicDecoder(
            vocab_size=self.vocab_size,
            embed_size=self.emb_dim,
            hidden_size=self.decoder_size,
            num_layers=self.dec_layers,
            memory_bank_size=self.num_directions * self.encoder_size,
            coverage_attn=self.coverage_attn,
            copy_attn=self.copy_attn,
            review_attn=self.review_attn,
            pad_idx=self.pad_idx_trg,
            attn_mode=self.attn_mode,
            dropout=self.dropout,
            hr_enc=self.hr_enc,
            out_sentiment_context=(self.dec_classify_input_type == 'attn_vec'),
            rating_memory_pred=self.rating_memory_pred
        )
        if self.bridge == 'dense':
            self.bridge_layer = nn.Linear(self.encoder_size * self.num_directions, self.decoder_size)
        elif opt.bridge == 'dense_nonlinear':
            self.bridge_layer = nn.tanh(nn.Linear(self.encoder_size * self.num_directions, self.decoder_size))
        else:
            self.bridge_layer = None
        if self.bridge == 'copy':
            assert self.encoder_size * self.num_directions == self.decoder_size, 'encoder hidden size and decoder hidden size are not match, please use a bridge layer'
        if self.share_embeddings:
            self.encoder.embedding.weight = self.decoder.embedding.weight
        self.init_embedding_weights()
    def init_embedding_weights(self):
        """Initialize weights."""
        init_range = 0.1
        self.encoder.embedding.weight.data.uniform_(-init_range, init_range)
        if not self.share_embeddings:
            self.decoder.embedding.weight.data.uniform_(-init_range, init_range)
        # fill with fixed numbers for debugging
        # self.embedding.weight.data.fill_(0.01)
        #self.encoder2decoder_hidden.bias.data.fill_(0)
        #self.encoder2decoder_cell.bias.data.fill_(0)
        #self.decoder2vocab.bias.data.fill_(0)
    def set_embedding(self, embedding):
        """embedding is the weight matrix"""
        assert self.share_embeddings
        # print("encoder embedding: {}".format(self.encoder.embedding.weight.size()))
        # print("pretrained embedding: {}".format(embedding.size()))
        assert self.encoder.embedding.weight.size() == embedding.size()
        self.encoder.embedding.weight.data.copy_(embedding)
    def forward(self, src, src_lens, trg, src_oov, max_num_oov, src_mask, trg_mask, rating, src_sent_positions, src_sent_nums, src_sent_mask):
        """
        :param src: a LongTensor containing the word indices of source sentences, [batch, src_seq_len], with oov words replaced by unk idx
        :param src_lens: a list containing the length of src sequences for each batch, with len=batch, with oov words replaced by unk idx
        :param trg: a LongTensor containing the word indices of target sentences, [batch, trg_seq_len]
        :param src_oov: a LongTensor containing the word indices of source sentences, [batch, src_seq_len], contains the index of oov words (used by copy)
        :param max_num_oov: int, max number of oov for each batch
        :param src_mask: a FloatTensor, [batch, src_seq_len]
        :param rating: a LongTensor, [batch]
        :param src_sent_positions: a LongTensor containing the forward and backward ending positions of src sentences, [batch, max_sent_num, 2]
        :param src_sent_nums: a list containing the sentence number of each src, [batch]
        :param src_sent_mask: a FloatTensor, [batch, max_sent_num]
        :return:
        """
        # print("Forward Pass")
        #print("in model")
        #print(src)
        batch_size, max_src_len = list(src.size())
        # Encoding
        memory_banks, encoder_final_states = self.encoder(src, src_lens, src_mask, src_sent_positions, src_sent_nums)
        word_memory_bank, sent_memory_bank = memory_banks
        word_encoder_final_state, sent_encoder_final_state = encoder_final_states
        src_masks = (src_mask, src_sent_mask)
        assert word_memory_bank.size() == torch.Size([batch_size, max_src_len, self.num_directions * self.encoder_size])
        assert word_encoder_final_state.size() == torch.Size([batch_size, self.num_directions * self.encoder_size])
        # classification
        if self.separate_layer_enc:
            classifier_memory_bank = sent_memory_bank
        else:
            classifier_memory_bank = word_memory_bank
        enc_classifier_output = self.enc_classifier(classifier_memory_bank, src_mask, sent_memory_bank, src_sent_mask)
        if isinstance(enc_classifier_output, tuple):
            enc_logit = enc_classifier_output[0]
            enc_classify_attn_dist = enc_classifier_output[1][0]
            sent_enc_classify_attn_dist = enc_classifier_output[1][1]
        else:
            enc_logit = enc_classifier_output
            enc_classify_attn_dist = None
            sent_enc_classify_attn_dist = None

        logit = (enc_logit)
        classifier_attention_dist = (enc_classify_attn_dist, sent_enc_classify_attn_dist)
        return  word_encoder_final_state, logit, classifier_attention_dist
    def tensor_2dlist_to_tensor(self, tensor_2d_list, batch_size, hidden_size, seq_lens):
        """
        :param tensor_2d_list: a 2d list of tensor with size=[hidden_size], len(tensor_2d_list)=batch_size, len(tensor_2d_list[i])=seq_len[i]
        :param batch_size:
        :param hidden_size:
        :param seq_lens: a list that store the seq len of each batch, with len=batch_size
        :return: [batch_size, hidden_size, max_seq_len]
        """
        # assert tensor_2d_list[0][0].size() == torch.Size([hidden_size])
        max_seq_len = max(seq_lens)
        for i in range(batch_size):
            for j in range(max_seq_len - seq_lens[i]):
                tensor_2d_list[i].append( torch.ones(hidden_size).to(self.device) * self.pad_idx_trg )  # [hidden_size]
            tensor_2d_list[i] = torch.stack(tensor_2d_list[i], dim=1)  # [hidden_size, max_seq_len]
        tensor_3d = torch.stack(tensor_2d_list, dim=0)  # [batch_size, hidden_size, max_seq_len]
        return tensor_3d

    def init_decoder_state(self, encoder_final_state):
        """
        :param encoder_final_state: [batch_size, self.num_directions * self.encoder_size]
        :return: [1, batch_size, decoder_size]
        """
        batch_size = encoder_final_state.size(0)
        if self.bridge == 'none':
            decoder_init_state = None
        elif self.bridge == 'copy':
            decoder_init_state = encoder_final_state
        else:
            decoder_init_state = self.bridge_layer(encoder_final_state)
        decoder_init_state = decoder_init_state.unsqueeze(0).expand((self.dec_layers, batch_size, self.decoder_size))
        # [dec_layers, batch_size, decoder_size]
        return decoder_init_state
    def init_context(self, memory_bank):
        # Init by max pooling, may support other initialization later
        context, _ = memory_bank.max(dim=1)
        return context
